# app/redis.py
"""
Redis Client Setup.
"""

import redis
from app.config import get_settings

settings = get_settings()

def get_redis_client():
    """Returns a synchronous Redis client."""
    return redis.from_url(settings.REDIS_URL, decode_responses=True)
