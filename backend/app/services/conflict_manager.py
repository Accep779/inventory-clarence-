"""
Adaptive Conflict Manager
========================
[ENGINE #6]: Stability Layer.
Prevents multiple agents from modifying the same product state simultaneously.
Uses Redis-based locking namespaced by merchant and SKU.
"""

import logging
import time
from typing import Optional
from app.redis import get_redis_client

logger = logging.getLogger(__name__)

class ConflictManager:
    LOCK_PREFIX = "agent_lock"
    DEFAULT_LOCK_TIME = 3600  # 1 hour
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self.redis = get_redis_client()
        
    def _get_lock_key(self, sku: str) -> str:
        return f"{self.merchant_id}:{self.LOCK_PREFIX}:{sku}"
        
    async def acquire_lock(self, sku: str, agent_type: str, ttl: int = DEFAULT_LOCK_TIME) -> bool:
        """
        Attempts to lock a SKU for a specific agent.
        """
        lock_key = self._get_lock_key(sku)
        # Using SET with NX (Set if Not eXists) and EX (Expire time)
        # In actual redis-py: r.set(k, v, nx=True, ex=ttl)
        try:
            # Note: redis-py client used in this project might be sync or async
            # from app.redis import get_redis_client returns a standard client
            success = self.redis.set(lock_key, agent_type, nx=True, ex=ttl)
            if success:
                logger.info(f"🔒 [Conflict] {agent_type} acquired lock for {sku}")
                return True
            else:
                current_owner = self.redis.get(lock_key)
                logger.warning(f"⚠️ [Conflict] {agent_type} blocked: {sku} is locked by {current_owner}")
                return False
        except Exception as e:
            logger.error(f"❌ ConflictManager error: {e}")
            return True # Fail open to prevent business stall, log error
            
    async def release_lock(self, sku: str):
        lock_key = self._get_lock_key(sku)
        try:
            self.redis.delete(lock_key)
            logger.info(f"🔓 [Conflict] Released lock for {sku}")
        except Exception as e:
            logger.error(f"❌ ConflictManager release error: {e}")
