# backend/app/services/tts_service.py
import requests
import uuid
import os
from datetime import datetime
from app.core.config import settings

# 音频保存目录
AUDIO_UPLOAD_DIR = settings.UPLOAD_DIR + "/audio"
os.makedirs(AUDIO_UPLOAD_DIR, exist_ok=True)

# ===== 百度 TTS 配置 =====
API_KEY = settings.voice_api_key
SECRET_KEY = settings.voice_secret_key

def get_access_token() -> str:
    """获取百度 API 的 access_token"""
    url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={API_KEY}&client_secret={SECRET_KEY}"
    
    try:
        response = requests.post(url)
        response.raise_for_status()
        result = response.json()
        token = result.get("access_token")
        if not token:
            print(f"❌ 获取 access_token 失败: {result}")
            return None
        print("✅ 获取 access_token 成功")
        return token
    except Exception as e:
        print(f"❌ 获取 access_token 异常: {e}")
        return None


def text_to_speech(text: str, voice: str = "0") -> str:
    """
    百度语音合成（TTS）
    
    Args:
        text: 要合成的文本（建议不超过60个汉字）
        voice: 发音人
            0: 度小美（女声，标准）
            1: 度小宇（男声）
            3: 度逍遥（男声，自然）
            4: 度丫丫（女声，童声）
    
    Returns:
        音频文件的 URL，失败返回 None
    """
    print(f"🔊 开始语音合成: {text[:20]}...")
    
    # 1. 获取 access_token
    token = get_access_token()
    if not token:
        return None
    
    # 2. 调用百度 TTS API
    url = "https://tsn.baidu.com/text2audio"
    
    params = {
        "tex": text,           # 文本
        "tok": token,          # access_token
        "cuid": "ai-assistant", # 用户标识
        "ctp": 1,              # 客户端类型
        "lan": "zh",           # 语言
        "spd": 5,              # 语速 0-9
        "pit": 5,              # 音调 0-9
        "vol": 5,              # 音量 0-9
        "per": int(voice),     # 发音人
        "aue": 3               # 返回格式：3=mp3
    }

    if len(text) > 512:
        params.tpn = 1
        params.tts_log = 1
    
    try:
        response = requests.get(url, params=params)
        
        # 检查返回的是音频还是错误信息
        content_type = response.headers.get('Content-Type', '')
        
        if 'audio' in content_type:
            # 成功：返回音频数据
            print(f"✅ TTS 合成成功，音频大小: {len(response.content)} bytes")
            
            # 3. 保存音频文件
            file_uuid = uuid.uuid4().hex[:12]
            date_str = datetime.now().strftime("%Y/%m/%d")
            save_dir = f"{AUDIO_UPLOAD_DIR}/{date_str}"
            os.makedirs(save_dir, exist_ok=True)
            
            filename = f"{file_uuid}.mp3"
            file_path = f"{save_dir}/{filename}"
            
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            audio_url = f"/uploads/audio/{date_str}/{filename}"
            print(f"🔊 音频已保存: {audio_url}")
            return audio_url
        else:
            # 失败：返回错误信息
            error_msg = response.text
            print(f"❌ TTS 合成失败: {error_msg}")
            return None
            
    except Exception as e:
        print(f"❌ TTS 异常: {e}")
        return None