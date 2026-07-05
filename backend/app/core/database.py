from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from .config import settings

# 创建异步引擎
engine = create_async_engine(
  settings.database_url,
  echo=settings.debug,
  future=True
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
  engine,
  class_=AsyncSession,
  expire_on_commit=False
)

# 创建基类，供模型继承
Base = declarative_base()

# 数据库会话依赖注入
async def get_db():
  async with AsyncSessionLocal() as session:
    try:
      yield session
    finally:
      await session.close()