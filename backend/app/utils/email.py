import httpx
from app.core.config import settings

async def send_email_async(to: str, subject: str, body: str) -> bool:
    """
    异步发送邮件（纯异步版本，供注册流程使用）
    返回 True 表示发送成功，False 表示发送失败
    """
    api_key = settings.email_api_key
    if not api_key:
        print("❌ 未配置 RESEND_API_KEY")
        return False

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": "onboarding@resend.dev",
        "to": [to],
        "subject": subject,
        "html": body
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                print(f"✅ 验证码邮件已发送到 {to}")
                return True
            else:
                error_msg = resp.json().get("message", "未知错误")
                print(f"❌ 邮件发送失败: {error_msg}")
                return False
    except Exception as e:
        print(f"❌ 邮件发送异常: {str(e)}")
        return False