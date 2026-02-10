# backend/app/middleware/idempotency.py
"""
Idempotency Middleware for API Operations.

Prevents duplicate operations from browsers that double-submit requests.
Uses Redis to store operation results with 24-hour TTL.

Usage:
    @router.post("/{id}/approve")
    async def approve_proposal(
        id: str,
        idempotency_key: str = Header(None, alias="Idempotency-Key"),
        ...
    ):
        return await idempotency_middleware.ensure_idempotent(
            key=idempotency_key,
            merchant_id=merchant_id,
            endpoint=f"/inbox/{id}/approve",
            handler=approve_internal,
            args=(id, session)
        )
"""

import json
import hashlib
import logging
from datetime import timedelta
from typing import Callable, Any, Optional

from app.redis import get_redis_client
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class IdempotencyError(Exception):
    """Raised for idempotency-related issues."""
    pass


class IdempotencyMiddleware:
    """
    Redis-backed idempotency for critical API operations.
    
    Features:
    - Caches operation results by idempotency key
    - 24-hour TTL for cached results
    - Per-merchant + endpoint scoping
    """
    
    TTL_HOURS = 24
    
    def __init__(self):
        self.redis = get_redis_client()
    
    async def ensure_idempotent(
        self,
        key: str,
        merchant_id: str,
        endpoint: str,
        handler: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute handler with idempotency protection.
        
        Args:
            key: Client-provided idempotency key (UUID recommended)
            merchant_id: Merchant making the request
            endpoint: API endpoint being called
            handler: Async function to execute
            *args, **kwargs: Arguments for handler
            
        Returns:
            Result from handler (or cached result if duplicate)
        """
        if not key:
            raise IdempotencyError("Idempotency-Key header is required for this operation")
        
        cache_key = self._build_cache_key(key, merchant_id, endpoint)
        
        # Check for existing result
        cached_result = self.redis.get(cache_key)
        if cached_result:
            logger.info(f"Idempotency cache hit for key {key[:8]}... - returning cached result")
            return json.loads(cached_result)
        
        # Execute operation
        try:
            result = await handler(*args, **kwargs)
            
            # Cache result
            self.redis.setex(
                cache_key,
                int(timedelta(hours=self.TTL_HOURS).total_seconds()),
                json.dumps(result, default=str)
            )
            
            logger.debug(f"Idempotency cached result for key {key[:8]}...")
            return result
            
        except Exception as e:
            # Don't cache errors - allow retry
            logger.error(f"Idempotency handler failed: {e}")
            raise
    
    def _build_cache_key(self, key: str, merchant_id: str, endpoint: str) -> str:
        """
        Build unique Redis key for this operation.
        
        Format: idempotency:{merchant_id}:{endpoint_hash}:{key}
        """
        endpoint_hash = hashlib.sha256(endpoint.encode()).hexdigest()[:8]
        return f"idempotency:{merchant_id}:{endpoint_hash}:{key}"
    
    def check_key_exists(self, key: str, merchant_id: str, endpoint: str) -> bool:
        """Check if an idempotency key has already been used."""
        cache_key = self._build_cache_key(key, merchant_id, endpoint)
        return self.redis.exists(cache_key) > 0
    
    def invalidate_key(self, key: str, merchant_id: str, endpoint: str) -> bool:
        """
        Invalidate a cached idempotency key (for rollbacks).
        
        Use sparingly - only for explicit undo operations.
        """
        cache_key = self._build_cache_key(key, merchant_id, endpoint)
        deleted = self.redis.delete(cache_key)
        if deleted:
            logger.info(f"Invalidated idempotency key {key[:8]}...")
        return deleted > 0


# Singleton instance
_idempotency_middleware = None


def get_idempotency_middleware() -> IdempotencyMiddleware:
    """Get or create the idempotency middleware singleton."""
    global _idempotency_middleware
    if _idempotency_middleware is None:
        _idempotency_middleware = IdempotencyMiddleware()
    return _idempotency_middleware
