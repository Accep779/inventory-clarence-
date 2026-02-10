# app/services/shadow_inventory.py
"""
Shadow Inventory Service
========================
Prevents overselling by maintaining temporary "holds" on inventory in Redis.

SECURITY FIX: Keys are now namespaced by merchant_id to prevent cross-tenant collisions.
"""

import logging
from typing import Optional, Dict, Any
from app.redis import get_redis_client

logger = logging.getLogger(__name__)

class ShadowInventory:
    """
    Redis-backed shadow ledger for inventory holds.
    
    IMPORTANT: Always instantiate with a merchant_id to ensure tenant isolation.
    """
    
    HOLD_PREFIX = "shadow_hold"
    DEFAULT_TTL = 600  # 10 minutes
    
    def __init__(self, merchant_id: str):
        """
        Initialize ShadowInventory for a specific merchant.
        
        Args:
            merchant_id: The merchant's UUID for tenant isolation.
        """
        self.merchant_id = merchant_id
        self.redis = get_redis_client()
    
    def _get_hold_key(self, sku: str) -> str:
        """Generate a tenant-namespaced Redis key."""
        return f"{self.merchant_id}:{self.HOLD_PREFIX}:{sku}"
    
    def reserve_stock(self, sku: str, quantity: int, real_stock: int, ttl: int = DEFAULT_TTL) -> bool:
        """Creates a temporary hold on inventory."""
        hold_key = self._get_hold_key(sku)
        
        try:
            current_holds = int(self.redis.get(hold_key) or 0)
            available = real_stock - current_holds
            
            if available < quantity:
                logger.warning(f"⛔ Insufficient shadow stock for {sku}. Available: {available}, Need: {quantity}")
                return False
            
            self.redis.incrby(hold_key, quantity)
            self.redis.expire(hold_key, ttl)
            
            logger.info(f"✅ Reserved {quantity} units of {sku} for merchant {self.merchant_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ ShadowInventory reserve failed: {e}")
            return False
    
    def commit_sale(self, sku: str, quantity: int) -> bool:
        """Clears hold after sale is confirmed."""
        hold_key = self._get_hold_key(sku)
        try:
            current = int(self.redis.get(hold_key) or 0)
            new_val = max(0, current - quantity)
            if new_val == 0:
                self.redis.delete(hold_key)
            else:
                self.redis.set(hold_key, new_val)
            return True
        except Exception as e:
            logger.error(f"❌ ShadowInventory commit failed: {e}")
            return False

    def get_available_quantity(self, sku: str, real_stock: int) -> int:
        """Real minus holds."""
        hold_key = self._get_hold_key(sku)
        current_holds = int(self.redis.get(hold_key) or 0)
        return max(0, real_stock - current_holds)
