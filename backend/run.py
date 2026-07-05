import uvicorn
import asyncio
from app.core.database import engine, Base

async def init_db():
    """导入所有模型并创建数据表"""
    # 在这里导入所有模型，确保它们被注册到 Base 上
    from app.models import User, Document, Conversation  # 👈 模型在这里导入
    
    print("📦 开始初始化数据库...")
    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
        print("✅ 数据库初始化完成")

async def main():
    # 启动前先初始化数据库
    await init_db()
    
    # 再启动 Uvicorn 服务器
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

if __name__ == "__main__":
    asyncio.run(main())