import random
import string
from app.utils.redis_client import get_redis
from app.utils.email import send_email_async

async def generate_and_send_code(email: str) -> dict:
    """
    生成6位验证码，存入 Redis，并发送到邮箱
    返回: {"success": True/False, "message": "..."}
    """
    # 1. 生成6位数字验证码
    code = ''.join(random.choices(string.digits, k=6))
    
    # 2. 存入 Redis，有效期5分钟
    redis = await get_redis()
    key = f"verify_code:{email}"
    await redis.setex(key, 300, code)  # 300秒 = 5分钟
    
    # 3. 构建邮件内容
    subject = "【AI 研发助理】注册验证码"
    body = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; max-width: 500px;">
        <h2 style="color: #667eea;">欢迎注册 AI 研发助理！</h2>
        <p>您的验证码是：</p>
        <div style="font-size: 36px; letter-spacing: 6px; font-weight: bold; color: #667eea; padding: 16px 0;">
            {code}
        </div>
        <p>验证码有效期为 <strong>5 分钟</strong>，请尽快使用。</p>
        <hr style="border: none; border-top: 1px solid #eee;">
        <p style="color: #999; font-size: 12px;">如果您没有注册账号，请忽略此邮件。</p>
    </div>
    """
    
    # 4. 发送邮件
    sent = await send_email_async(email, subject, body)
    
    if sent:
        return {"success": True, "message": "验证码已发送"}
    else:
        return {"success": False, "message": "邮件发送失败，请稍后重试"}

async def verify_code(email: str, code: str) -> bool:
    """验证验证码是否正确且未过期"""
    redis = await get_redis()
    key = f"verify_code:{email}"
    stored = await redis.get(key)
    
    if stored is None:
        return False
    
    return stored == code

async def delete_code(email: str):
    """删除验证码（注册成功后调用）"""
    redis = await get_redis()
    key = f"verify_code:{email}"
    await redis.delete(key)