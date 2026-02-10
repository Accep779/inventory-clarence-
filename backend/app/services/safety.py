# app/services/safety.py
"""
Safety & Emergency Control Service
=================================
Centralized logic for checking "Global Kill Switches" and merchant-level pauses.
"""

import logging
from typing import Optional
from redis import Redis
from sqlalchemy import select
from app.database import async_session_maker
from app.models import Merchant
import os

logger = logging.getLogger(__name__)

class SafetyService:
    """
    Handles emergency pauses and safety checks before high-risk operations.
    """
    
    GLOBAL_PAUSE_KEY = "cephly:global_pause"
    
    def __init__(self, merchant_id: Optional[str] = None):
        self.merchant_id = merchant_id
        # Use shared redis connection if available, otherwise create one
        self.redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    async def is_paused(self) -> bool:
        """
        Check if the system is paused globally or for a specific merchant.
        """
        # 1. Check Global Pause (Redis)
        global_pause = self.redis.get(self.GLOBAL_PAUSE_KEY)
        if global_pause and global_pause.decode('utf-8') == "true":
            logger.warning("🚨 [Safety] GLOBAL KILL SWITCH DETECTED")
            return True
            
        # 2. Check Merchant-specific Pause (DB)
        if self.merchant_id:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(Merchant.is_paused).where(Merchant.id == self.merchant_id)
                )
                merchant_paused = result.scalar_one_or_none()
                if merchant_paused:
                    logger.warning(f"⚠️ [Safety] Merchant {self.merchant_id} is PAUSED")
                    return True
                    
        return False

    def toggle_global_pause(self, state: bool):
        """
        Emergency toggle for all operations.
        """
        self.redis.set(self.GLOBAL_PAUSE_KEY, "true" if state else "false")
        action = "ACTIVATED" if state else "DEACTIVATED"
        logger.info(f"🛑 [Safety] GLOBAL KILL SWITCH {action}")
