from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from jose import JWTError, jwt
from sqlalchemy import select

from app.core.database import get_db
from app.models.user import User
from app.utils.security import hash_password, verify_password
from app.core.config import settings
from app.services.code_service import generate_and_send_code, verify_code, delete_code

router = APIRouter(prefix="/auth", tags=["认证"])

# ---------- 请求/响应模型 ----------
# 新增：发送验证码请求
class SendCodeRequest(BaseModel):
    email: EmailStr

class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str   

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    code: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    username: str
    email: str

# ---------- 辅助函数 ----------
def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """生成 JWT Token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

# ========== 发送验证码接口 ==========

@router.post("/send-code")
async def send_code(
    request: SendCodeRequest,
    db: AsyncSession = Depends(get_db)
):
    """发送注册验证码到邮箱"""
    # 1. 检查邮箱是否已被注册
    stmt = select(User).where(User.email == request.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册"
        )
    
    # 2. 生成验证码并发送
    result = await generate_and_send_code(request.email)
    
    if result["success"]:
        return {"message": result["message"], "email": request.email}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["message"]
        )

@router.post("/verify-code")
async def verify_code_endpoint(request: VerifyCodeRequest):
    """验证验证码是否正确"""
    from app.services.code_service import verify_code
    
    is_valid = await verify_code(request.email, request.code)
    
    if is_valid:
        return {"valid": True, "message": "验证码正确"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码无效或已过期"
        )       

# ========== 注册接口（修改版） ==========

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """用户注册（需要验证码）"""
    
    # 1. 检查用户名是否已存在
    stmt = select(User).where(User.username == request.username)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被注册"
        )
    
    # 2. 检查邮箱是否已存在
    stmt = select(User).where(User.email == request.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )
    
    # 3. 验证验证码
    is_valid = await verify_code(request.email, request.code)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码无效或已过期"
        )
    
    # 4. 创建用户
    new_user = User(
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password)
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # 5. 删除已使用的验证码
    await delete_code(request.email)
    
    return UserResponse(
        id=new_user.id,
        username=new_user.username,
        email=new_user.email
    )

# ---------- 登录接口 ----------
@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """用户登录，返回 JWT Token"""
    from sqlalchemy import select
    stmt = select(User).where(User.username == request.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id}
    )
    
    return TokenResponse(access_token=access_token)