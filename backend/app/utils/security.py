from passlib.context import CryptContext

# 支持 bcrypt 和 argon2，优先使用 argon2 加密新密码
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    argon2__rounds=4,  # 加快 argon2 速度（开发环境）
)

def hash_password(password: str) -> str:
    """对明文密码进行哈希加密（使用 argon2）"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否与哈希密码匹配（自动识别算法）"""
    return pwd_context.verify(plain_password, hashed_password)