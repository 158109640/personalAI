import asyncio
import httpx
from app.core.config import settings

# ---------- 异步邮件发送逻辑 ----------
async def _send_email_async(to: str, subject: str, body: str) -> str:
    """异步发送邮件（直接调用 Resend API）"""
    api_key = settings.email_api_key
    if not api_key:
        return "未配置 EMAIL_API_KEY，请在 .env 文件中设置"

    url = settings.email_base_url
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": "onboarding@resend.dev",
        "to": [to],  # 确保 to 是一个列表
        "subject": subject,
        "html": body
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            print(f"📧 正在发送邮件到: {to}")
            # 关键：使用 json=payload 而不是 data=payload
            resp = await client.post(url, json=payload, headers=headers)
            
            # 打印响应详情，方便调试
            print(f"📥 响应状态码: {resp.status_code}")
            print(f"📥 响应内容: {resp.text}")
            
            if resp.status_code == 200:
                data = resp.json()
                return f"✅ 邮件已成功发送到 {to}，邮件 ID: {data.get('id')}"
            else:
                error_msg = resp.json().get("message", "未知错误")
                return f"❌ 邮件发送失败：{error_msg}"
                
    except httpx.TimeoutException:
        return "邮件服务请求超时，请稍后再试"
    except Exception as e:
        return f"邮件发送失败：{str(e)}"

# ---------- 同步包装器（供 LangChain Agent 调用） ----------
def send_email(to: str, subject: str, body: str) -> str:
    """
    发送邮件（同步函数，供 Agent 工具使用）
    """
    try:
        return asyncio.run(_send_email_async(to, subject, body))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_send_email_async(to, subject, body))
        finally:
            loop.close()
    except Exception as e:
        return f"邮件发送失败：{str(e)}"

async def send_email_async(to: str, subject: str, body: str) -> str:
    return await _send_email_async(to, subject, body)
