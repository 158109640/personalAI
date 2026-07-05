from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
import shutil
import os
import uuid
from app.services.rag_service import rag_service
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.core.database import get_db
from app.models.document import Document, DocumentStatus
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/documents", tags=["文档管理"])

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    sources: Optional[List[str]] = None

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """上传文档，并创建向量索引"""
    
    # 生成唯一文档 ID
    doc_id = f"{session_id}_{uuid.uuid4().hex[:8]}"
    
    # 保存文件
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # 加载并切分文档
        texts = rag_service.load_document(file_path, file.filename)
        collection_name = rag_service.create_vector_store(doc_id, texts, file.filename)
        
        # 创建向量存储
        store_path = rag_service.create_vector_store(doc_id, texts, file.filename)
        
        # 🔥 保存文档记录到数据库
        new_doc = Document(
            doc_id=doc_id,
            filename=file.filename,
            file_path=file_path,
            content="\n".join(texts[:3]) if texts else "",
            status=DocumentStatus.PROCESSED,
            owner_id=current_user.id,
            collection_name=collection_name
        )
        db.add(new_doc)
        await db.commit()
        
        print(f"✅ 文档记录已保存到数据库: {doc_id}")
        
        return {
            "success": True,
            "doc_id": doc_id,
            "filename": file.filename,
            "chunks": len(texts),
            "message": f"文档 {file.filename} 已处理完成"
        }
    except Exception as e:
        # 处理失败时清理文件
        if os.path.exists(file_path):
            os.remove(file_path)
        print(f"❌ 文档处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")

@router.post("/query")
async def query_document(
    request: QueryRequest,
    doc_id: str,
    current_user: User = Depends(get_current_user)
):
    """基于文档回答问题（自动判断相关性，不相关时自动降级）"""
    
    from app.services.ai_service import ai_service
    from app.services.agent_service import agent_service
    
    # 1. 检索相关片段
    sources = rag_service.search(doc_id, request.question, top_k=3)
    
    # 如果没有检索到任何片段，直接走普通对话
    if not sources:
        print("📊 未检索到任何片段，走普通对话")
        response = await agent_service.chat([{"role": "user", "content": request.question}])
        return QueryResponse(answer=response, sources=[])
    
    # 2. 用大模型判断相关性（更精确）
    relevance_prompt = f"""判断用户问题是否与以下文档片段相关。只返回 "相关" 或 "不相关"。

文档片段：
{sources[0][:300]}

用户问题：{request.question}

只返回 "相关" 或 "不相关"，不要有任何其他内容。"""
    
    check_messages = [{"role": "user", "content": relevance_prompt}]
    relevance_result = ai_service.get_response(check_messages)
    
    # 精确判断：只有明确包含"相关"才认为是相关
    relevance_result = relevance_result.strip()
    is_relevant = "相关" in relevance_result and "不相关" not in relevance_result
    
    print(f"📊 相关性判断结果: '{relevance_result}' -> {'相关' if is_relevant else '不相关'}")
    
    # 3. 如果不相关，自动降级到普通对话
    if not is_relevant:
        print("📊 文档不相关，自动降级到普通对话")
        response = await agent_service.chat([{"role": "user", "content": request.question}])
        return QueryResponse(answer=response, sources=[])
    
    # 4. 相关性足够，基于文档回答
    context = "\n\n".join(sources)
    prompt = f"""请根据以下文档片段回答用户的问题。如果片段中没有相关信息，请直接说"文档中没有提到相关内容"。

文档片段：
{context}

用户问题：{request.question}

请基于文档片段给出准确、简洁的回答。"""
    
    messages = [{"role": "user", "content": prompt}]
    answer = ai_service.get_response(messages)
    
    return QueryResponse(answer=answer, sources=sources)

VECTOR_STORE_DIR = "vector_store"   

@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除文档及其向量存储"""
    from sqlalchemy import select, delete
    
    # 1. 查找文档
    stmt = select(Document).where(
        Document.doc_id == doc_id,
        Document.owner_id == current_user.id
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    # 2. 删除向量存储文件
    store_path = os.path.join(VECTOR_STORE_DIR, doc.doc_id)
    if os.path.exists(store_path):
        import shutil
        try:
            shutil.rmtree(store_path)
            print(f"🗑️ 已删除向量存储: {store_path}")
        except Exception as e:
            print(f"⚠️ 删除向量存储失败: {e}")
    
    # 3. 删除上传的文件
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
            print(f"🗑️ 已删除文件: {doc.file_path}")
        except Exception as e:
            print(f"⚠️ 删除文件失败: {e}")
    
    # 4. 删除数据库记录
    await db.delete(doc)
    await db.commit()
    
    return {"message": f"文档 {doc.filename} 已删除"}   