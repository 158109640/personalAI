from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.user import User
from app.core.config import settings

# ---------- 1. 定义 OAuth2 认证方案 ----------
# 这行代码告诉 FastAPI：“我们使用 JWT Token 进行认证，Token 是通过 /auth/login 接口获取的。”
# oauth2_scheme 会从请求头中提取 "Authorization: Bearer <token>" 里的 token 字符串。
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ---------- 2. 核心函数：从 Token 中获取当前用户 ----------
async def get_current_user(
    token: str = Depends(oauth2_scheme),      # ① 从请求头中提取 Token
    db: AsyncSession = Depends(get_db)         # ② 获取数据库会话
) -> User:
    """从 JWT Token 中获取当前用户"""
    
    # 定义认证失败的统一响应（401 未授权）
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # ---------- 3. 解码并验证 Token ----------
    try:
        # 用密钥解码 JWT Token，验证其合法性
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        # 从 Token 负载中提取用户 ID 和用户名（这些数据是登录时存入的）
        user_id: int = payload.get("user_id")
        username: str = payload.get("sub")
        # 如果缺少这两个字段，说明 Token 是无效的
        if user_id is None or username is None:
            raise credentials_exception
    except JWTError:
        # Token 无法解码（过期、篡改或格式错误）
        raise credentials_exception
    
    # ---------- 4. 根据用户 ID 查询数据库 ----------
    # 构建查询：SELECT * FROM users WHERE id = user_id
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    # 如果数据库中没有这个用户（比如用户已被删除）
    if user is None:
        raise credentials_exception
    
    # ---------- 5. 返回用户对象 ----------
    # 如果一切正常，返回 User 对象，后续接口可以直接使用 current_user.id、current_user.username 等
    return user