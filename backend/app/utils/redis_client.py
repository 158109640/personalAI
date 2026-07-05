import redis.asyncio as redis
from app.core.config import settings

redis_client = None

async def get_redis():
    """获取 Redis 连接（单例模式）"""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True  # 自动解码为字符串
        )
    return redis_client

async def close_redis():
    """关闭 Redis 连接"""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None