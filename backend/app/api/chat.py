from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.services.agent_service import agent_service
from app.services.conversation_service import conversation_service
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.conversation import Conversation
from app.services.multi_agent_service import multi_agent
from app.services.upload_service import upload_service

router = APIRouter(prefix="/chat", tags=["对话"])

# ========== 模型定义 ==========
class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: int
    status: str = ""
    type: str = ""

class NeedToolRequest(BaseModel):
    message: str

class NeedToolResponse(BaseModel):
    need_tool: bool
    use_rag: bool = False

# ========== 判断是否需要工具（前端调用）==========
@router.post("/need-tool", response_model=NeedToolResponse)
async def check_need_tool(
    message: str = Form(...),
    current_user: User = Depends(get_current_user),
    files: List[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db)
):
    """判断用户消息是否需要调用工具（用于前端选择流式/非流式）"""
    
    # 1. 先检查是否有上传文档，如果有且相关，就走 RAG
    stmt = select(Document).where(
        Document.owner_id == current_user.id,
        Document.status == 'processed'
    )
    result = await db.execute(stmt)
    docs = result.scalars().all()
    
    if docs:
        from app.services.rag_service import rag_service
        doc_ids = [doc.doc_id for doc in docs]
        best_chunks = await rag_service.search_all_documents(
            doc_ids=doc_ids,
            query=message,
            top_k_per_doc=3,
            final_top_k=3
        )
        
        if best_chunks and best_chunks[0]['score'] > 0.1:
            return NeedToolResponse(need_tool=False, use_rag=True)
    
    # 2. 如果有图片，判断是否需要工具
    if files:
        prompt = f"""用户上传了图片，并说：{message if message else '请描述这张图片'}
        判断用户是否还需要调用外部工具（如天气、搜索、邮件）。
        如果用户只是想了解图片内容 → 返回 false
        如果用户同时问天气、新闻等 → 返回 true
        只返回 true 或 false"""
        
        response = await agent_service.chat([{"role": "user", "content": prompt}])
        need_tool = "true" in response.lower()
        return NeedToolResponse(need_tool=need_tool, use_rag=False)
    
    # 3. 普通情况，使用模型判断
    prompt = f"""判断用户是否需要调用外部工具来回答这个问题。
    用户问题：{message}
    判断规则：
    - 如果需要查天气、搜索、发邮件等 → 返回 true
    - 如果可以直接回答 → 返回 false
    只返回 true 或 false，不要有其他内容。"""
    
    response = await agent_service.chat([{"role": "user", "content": prompt}])
    need_tool = "true" in response.lower()
    return NeedToolResponse(need_tool=need_tool)

# ========== 普通对话接口 ==========
@router.post("")
async def chat(
    message: str = Form(...),
    conversation_id: Optional[int] = Form(None),
    files: List[UploadFile] = File(default=[]),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """与 AI 对话（自动判断 RAG/工具/普通对话）"""
    
    # 1. 获取或创建会话
    conv = await conversation_service.get_or_create_conversation(
        db, current_user, conversation_id
    )
    
    # 2. 保存文件消息
    processed_files = []
    if files:
        for file in files:
            file_info = await upload_service.upload_file(file, current_user.id)
            # 重命名键以匹配 add_message 期望的格式
            processed_files.append({
                "file_url": file_info["url"],
                "file_name": file_info["name"],
                "file_size": file_info["size"],
                "file_type": file_info["type"]
            })
    
    # 保存用户消息
    await conversation_service.add_message(
        db, 
        conv.id, 
        "user", 
        message or f"[上传了 {len(files)} 张图片]", 
        processed_files
    )        
    
    # 如果有图片，走多模态
    if files:
        from app.services.vision_service import multimodal_chat
        history = await conversation_service.get_conversation_messages(db, conv.id)
        response = await multimodal_chat(
            text=message,
            image_files=files,
            history=history
        )
        
        await conversation_service.add_message(db, conv.id, "assistant", response)
        
        return ChatResponse(response=response, conversation_id=conv.id)

    # 3.获取历史消息
    history = await conversation_service.get_conversation_messages(db, conv.id) if conv.id else []    
    
    # 3. 判断该走哪个流程
    result = await multi_agent.ainvoke({
        "query": message,
        "messages": history,
        "research_result": "",
        "final_answer": "",
        "next_step": "",
        "user_id": current_user.id,
        "reply_type": "",
        "audio_url": ""
    })
    
    type = result["reply_type"]
    print('这里是类型:', type)
    answer = result["final_answer"] if type == "text" else result["audio_url"]
    # 4. 保存 AI 回复
    print('到这里了 哈哈哈哈', answer)
    await conversation_service.add_message(db, conv.id, "assistant", answer, processed_files, type)
    print('到哪里了 哈哈哈哈')
    # 5. 更新标题（如果是新对话）
    msg_count = len(await conversation_service.get_conversation_messages(db, conv.id))
    if msg_count <= 2:
        title = message[:50] + ("..." if len(message) > 50 else "")
        await conversation_service.update_conversation_title(db, conv.id, title)

    return ChatResponse(response=answer, conversation_id=conv.id, status="✅ 回答完成", type=type)

# ========== 流式对话接口 ==========
@router.post("/stream")
async def chat_stream(
    message: str = Form(...),
    conversation_id: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    files: List[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db)
):
    """流式对话接口（自动判断 RAG/工具/普通对话）"""
    
    # 1. 获取或创建会话
    conv = await conversation_service.get_or_create_conversation(
        db, current_user, conversation_id
    )
    
    # 2. 保存用户消息
    processed_files = []
    if files:
        for file in files:
            file_info = await upload_service.upload_file(file, current_user.id)
            # 重命名键以匹配 add_message 期望的格式
            processed_files.append({
                "file_url": file_info["url"],
                "file_name": file_info["name"],
                "file_size": file_info["size"],
                "file_type": file_info["type"]
            })

    await conversation_service.add_message(
        db, 
        conv.id, 
        "user", 
        message or f"[上传了 {len(files)} 张图片]", 
        processed_files
    )
    
    # 3. 获取历史消息
    history = await conversation_service.get_conversation_messages(db, conv.id)
    # 4. 定义生成器
    async def generate():
        import asyncio
        from app.services.multi_agent_service import stream_multi_agent
        
        full_answer = ""
        # 先返回会话 ID，让前端更新临时 ID
        yield f"data: {json.dumps({'type': 'conversation_id', 'conversation_id': conv.id})}\n\n"
        if files:
            from app.services.vision_service import multimodal_chat
            # 使用不同的变量名避免和外部变量冲突
            current_history = await conversation_service.get_conversation_messages(db, conv.id)
            response = await multimodal_chat(
                text=message,
                image_files=files,
                history=current_history
            )
            # 逐字返回，添加小延迟避免缓冲
            for char in response:
                full_answer += char
                yield f"data: {json.dumps({'type': 'content', 'content': char, 'done': False})}\n\n"
                await asyncio.sleep(0.01)  # 小延迟，让数据被立即发送
            
            # 保存 AI 回复
            await conversation_service.add_message(db, conv.id, "assistant", full_answer, processed_files)
            
            # 更新标题
            msg_count = len(await conversation_service.get_conversation_messages(db, conv.id))
            if msg_count <= 2:
                title = message[:50] + ("..." if len(message) > 50 else "")
                await conversation_service.update_conversation_title(db, conv.id, title)
            
            yield f"data: {json.dumps({'done': True})}\n\n"
        else:
            # 使用真正的流式函数
            reply_type = 'text'
            async for chunk in stream_multi_agent(
                query=message,
                messages=history,
                user_id=current_user.id
            ):
                if chunk["type"] == "status":
                    yield f"data: {json.dumps({'type': 'status', 'content': chunk['content']})}\n\n"
                elif chunk["type"] == "reply_type":
                    reply_type = chunk["content"]
                elif chunk["type"] == "audio":
                    full_answer += chunk["content"]
                    yield f"data: {json.dumps({'type': 'audio', 'content': chunk['content']})}\n\n"
                elif chunk["type"] == "content":
                    full_answer += chunk["content"]
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk['content'], 'done': False})}\n\n"
                elif chunk["type"] == "done":
                    # 保存 AI 回复
                    await conversation_service.add_message(db, conv.id, "assistant", full_answer, processed_files, reply_type)
                    
                    # 更新标题
                    msg_count = len(await conversation_service.get_conversation_messages(db, conv.id))
                    if msg_count <= 2:
                        title = message[:50] + ("..." if len(message) > 50 else "")
                        await conversation_service.update_conversation_title(db, conv.id, title)
                    
                    yield f"data: {json.dumps({'done': True})}\n\n"
    
    return StreamingResponse(
        generate(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 Nginx 缓冲
        }
    )  

# ========== 会话管理接口 ==========
@router.get("/conversations")
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的所有会话列表"""
    convs = await conversation_service.get_user_conversations(db, current_user)
    return {
        "conversations": [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat()
            }
            for c in convs
        ]
    }

@router.get("/conversations/{conversation_id}")
async def get_conversation_messages(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 10,
    offset: int = 0
):
    """获取指定会话的所有消息"""
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    messages = await conversation_service.get_conversation_messages(db, conversation_id, limit, offset)
    return {"messages": messages}

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除指定会话"""
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    await db.delete(conv)
    await db.commit()
    return {"message": "会话已删除"}
