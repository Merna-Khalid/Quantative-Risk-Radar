import redis.asyncio as redis
import os
import pickle
import logging
from typing import Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

class RedisCache:
    _instance: Optional[redis.Redis] = None
    
    @classmethod
    async def get_client(cls) -> Optional[redis.Redis]:
        if cls._instance is None:
            await cls._initialize()
        return cls._instance
    
    @classmethod
    async def _initialize(cls):
        try:
            cls._instance = await redis.from_url(REDIS_URL, decode_responses=False)
            await cls._instance.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            cls._instance = None
    
    @classmethod
    async def close(cls):
        if cls._instance:
            await cls._instance.close()
            cls._instance = None
            logger.info("Redis connection closed")


async def get_redis_client() -> Optional[redis.Redis]:
    return await RedisCache.get_client()

async def init_redis():
    await RedisCache._initialize()

async def close_redis():
    await RedisCache.close()

async def get_cached_data(cache_key: str):
    client = await RedisCache.get_client()
    if not client:
        logger.warning("Redis client not available")
        return None
    
    try:
        cached = await client.get(cache_key)
        if cached:
            return pickle.loads(cached)
    except Exception as e:
        logger.warning(f"Error loading cached data for key {cache_key}: {e}")
    return None

async def set_cached_data(cache_key: str, data, expire_seconds: int = 3600):
    client = await RedisCache.get_client()
    if not client:
        logger.warning("Redis client not available, skipping cache")
        return False
    
    try:
        serialized_data = pickle.dumps(data)
        await client.set(cache_key, serialized_data, ex=expire_seconds)
        logger.info(f"Data cached successfully with key: {cache_key}")
        return True
    except Exception as e:
        logger.warning(f"Error caching data for key {cache_key}: {e}")
        return False
    

RISK_CACHE_KEY = "risk_engine:current_full_risk"
SYSTEMIC_CACHE_KEY = "risk_engine:systemic_snapshot"
QUANTILE_CACHE_KEY = "risk_engine:quantile_snapshot"


async def cache_full_risk(data: dict, expire_seconds: int = 900):
    return await set_cached_data(RISK_CACHE_KEY, data, expire_seconds)


async def get_cached_full_risk() -> Optional[dict]:
    return await get_cached_data(RISK_CACHE_KEY)


async def cache_systemic_snapshot(data: dict, expire_seconds: int = 900):
    return await set_cached_data(SYSTEMIC_CACHE_KEY, data, expire_seconds)


async def get_cached_systemic_snapshot() -> Optional[dict]:
    return await get_cached_data(SYSTEMIC_CACHE_KEY)


async def cache_quantile_snapshot(data: dict, expire_seconds: int = 900):
    return await set_cached_data(QUANTILE_CACHE_KEY, data, expire_seconds)


async def get_cached_quantile_snapshot() -> Optional[dict]:
    return await get_cached_data(QUANTILE_CACHE_KEY)
