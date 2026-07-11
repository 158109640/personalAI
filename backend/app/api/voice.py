# backend/app/api/voice.py
import tempfile
import os
import subprocess
import json
import uuid
import shutil
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from aip import AipSpeech
from app.core.config import settings
from app.services.multi_agent_service import stream_multi_agent
from app.services.conversation_service import conversation_service
from app.core.database import get_db
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/voice", tags=["语音"])

# ========== 百度语音配置 ==========
APP_ID = settings.voice_api_id
API_KEY = settings.voice_api_key
SECRET_KEY = settings.voice_secret_key
client = AipSpeech(APP_ID, API_KEY, SECRET_KEY)

# 音频保存目录
AUDIO_UPLOAD_DIR = os.path.join(settings.UPLOAD_DIR, "audio")
os.makedirs(AUDIO_UPLOAD_DIR, exist_ok=True)

# 允许的音频格式
ALLOWED_AUDIO_EXTS = {'.mp3', '.wav', '.m4a', '.amr', '.aac', '.flac', '.ogg', '.webm'}


@router.post("/voice-to-text")
async def voice_to_text(
    audio: UploadFile = File(...),
    conversation_id: int = Form(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    接收音频文件：
    1. 保存音频文件到服务器
    2. 识别文字
    3. 调用多 Agent 流式处理
    4. 返回音频URL + 识别文字 + AI回复
    """
    tmp_path = None
    wav_path = None
    
    try:
        # 1. 检查并保存音频文件
        filename = audio.filename or "recording.webm"
        ext = os.path.splitext(filename)[1].lower()
        
        if ext not in ALLOWED_AUDIO_EXTS and not audio.content_type.startswith("audio/"):
            raise HTTPException(400, f"请上传音频文件，当前文件类型: {audio.content_type}")
        
        # 保存临时文件
        with tempfile.NamedTemporaryFile(suffix=ext if ext else ".webm", delete=False) as tmp:
            content = await audio.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # 2. 永久保存音频文件
        file_uuid = uuid.uuid4().hex[:12]
        date_str = datetime.now().strftime("%Y/%m/%d")
        save_dir = os.path.join(AUDIO_UPLOAD_DIR, date_str)
        os.makedirs(save_dir, exist_ok=True)
        
        saved_filename = f"{file_uuid}.webm"
        saved_audio_path = os.path.join(save_dir, saved_filename)
        shutil.copy2(tmp_path, saved_audio_path)
        audio_url = f"/uploads/audio/{date_str}/{saved_filename}"
        
        # 3. 获取或创建会话
        conversation = await conversation_service.get_or_create_conversation(db, user, conversation_id)


        
        # 保存用户语音消息
        await conversation_service.add_message(
            db, conversation.id, "user", audio_url, [], "audio"
        )
        
        # 4. 百度语音识别（需要转换为 WAV）
        if ext != '.wav':
            wav_path = tmp_path + ".wav"
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-i", tmp_path,
                        "-ar", "16000",
                        "-ac", "1",
                        "-c:a", "pcm_s16le",
                        wav_path,
                        "-y"
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                with open(wav_path, 'rb') as f:
                    audio_data = f.read()
            except subprocess.CalledProcessError as e:
                raise HTTPException(500, f"音频格式转换失败: {e.stderr.decode()}")
        else:
            with open(tmp_path, 'rb') as f:
                audio_data = f.read()
        
        # 调用百度语音识别
        result = client.asr(audio_data, 'wav', 16000, {'dev_pid': 1537})
        
        # 清理临时文件
        for path in [tmp_path, wav_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except:
                    pass
        
        if result.get('err_no') != 0:
            raise HTTPException(400, f"识别失败: {result.get('err_msg', '未知错误')}")
        
        recognized_text = result['result'][0]
        
        # 5. 获取对话历史
        messages_data = await conversation_service.get_conversation_messages(
            db, conversation.id, limit=10, offset=0
        )
        
        audio_size = os.path.getsize(saved_audio_path)
        
        # 6. 返回流式响应
        async def generate():
            """生成流式响应"""
            
            yield f"{json.dumps({'type': 'conversation_id', 'conversation_id': conversation.id})}\n\n"
            print(f"会话ID: {conversation.id}")
            
            # 1. 先发送语音信息
            yield json.dumps({
                "type": "audio",
                "recognized_text": recognized_text,
                "audio_url": audio_url,
                "audio_size": audio_size
            }, ensure_ascii=False) + "\n"
            
            # 2. 调用多 Agent
            full_reply = ""
            type = ""
            async for chunk in stream_multi_agent(
                query=recognized_text,
                messages=messages_data,
                user_id=user.id
            ):
                # chunk 是字典，直接转 JSON 字符串
                if isinstance(chunk, dict):
                    yield json.dumps(chunk, ensure_ascii=False) + "\n"
                    if chunk.get("type") == "content":
                        full_reply += chunk.get("content", "")
                        type = "content"
                    elif chunk.get("type") == "audio":
                        full_reply += chunk.get("content", "")
                        type = "audio"
    
                elif isinstance(chunk, str):
                    try:
                        data = json.loads(chunk)
                        yield json.dumps(data, ensure_ascii=False) + "\n"
                        if data.get("type") == "content":
                            full_reply += data.get("content", "")
                            type = "content"
                        elif data.get("type") == "audio":
                            full_reply += data.get("content", "")
                            type = "audio"
                        elif data.get("type") == "conversation_id":
                            print('需要更新会话了')
                            type = "conversation_id"
                    except json.JSONDecodeError:
                        yield json.dumps({
                            "type": "content",
                            "content": chunk
                        }, ensure_ascii=False) + "\n"
                        full_reply += chunk
                        type = "content"
                else:
                    yield json.dumps({
                        "type": "content",
                        "content": str(chunk)
                    }, ensure_ascii=False) + "\n"
                    full_reply += str(chunk)
                    type = "content"
            
            # 3. 保存 AI 回复到数据库
            if full_reply:
                await conversation_service.add_message(
                    db, conversation.id, "assistant", full_reply, [], type
                )
            
            # 4. 发送完成信号
            yield json.dumps({"type": "done"}, ensure_ascii=False) + "\n"
        
        # ===== 🔥 关键改动：使用 text/event-stream 或 application/json =====
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",  # ← 改用 SSE 格式
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # 禁用 Nginx 缓冲
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        # 清理临时文件
        for path in [tmp_path, wav_path]:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except:
                    pass
        raise HTTPException(500, f"语音识别失败: {str(e)}")