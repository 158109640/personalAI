import base64
import httpx
from typing import List, Optional, Dict
from fastapi import UploadFile
from app.core.config import settings

async def multimodal_chat(
    text: str,
    image_files: List[UploadFile],
    history: List[Dict[str, str]] = None
) -> str:
    """
    多模态对话：支持图片 + 文字
    """
    if not settings.vl_api_key:
        return "请先配置 VL_API_KEY 环境变量"
    
    # 1. 读取图片并转为 base64
    image_contents = []
    for file in image_files[:5]:  # 最多5张
        try:
            image_data = await file.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')
            content_type = file.content_type or "image/jpeg"
            image_contents.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{content_type};base64,{base64_image}"
                }
            })
        except Exception as e:
            print(f"读取图片失败: {e}")
    
    # 2. 构建消息
    messages = []
    
    print(history, '这是历史啊')
    # 添加历史对话
    if history:
        for msg in history.get('data', [])[-5:]:
            messages.append({
                "role": "user" if msg["role"] == "user" else "assistant",
                "content": msg["content"]
            })
    
    # 构建当前消息
    current_content = []
    if text:
        current_content.append({"type": "text", "text": text})
    current_content.extend(image_contents)
    
    if not current_content:
        return "请上传图片或输入文字"
    
    messages.append({
        "role": "user",
        "content": current_content
    })
    
    # 3. 调用模型
    url = f"{settings.vl_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.vl_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.vl_model,
        "messages": messages,
        "max_tokens": 1000
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                error_detail = resp.text
                return f"模型调用失败 ({resp.status_code}): {error_detail[:200]}"
    except Exception as e:
        return f"请求失败: {str(e)}"