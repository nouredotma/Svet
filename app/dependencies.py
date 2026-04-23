from collections.abc import AsyncGenerator

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.session import AsyncSessionLocal, get_db


async def get_redis() -> AsyncGenerator[Redis, None]:
    settings = get_settings()
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


__all__ = [
    "AsyncSessionLocal",
    "get_db",
    "get_redis",
    "get_settings",
    "Settings",
    "AsyncSession",
]
