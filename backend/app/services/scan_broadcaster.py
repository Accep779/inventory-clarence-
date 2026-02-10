"""
Scan Broadcaster Service - Redis Pub/Sub for Live Scan Updates.

Enables real-time communication between Celery background tasks
and SSE endpoints for the onboarding scanning experience.
"""

import json
import logging
from typing import Dict, Any, Optional
from app.redis import get_redis_client

logger = logging.getLogger(__name__)


class ScanBroadcaster:
    """
    Redis pub/sub broadcaster for live scan updates.
    
    Usage:
    - Celery task publishes: broadcaster.publish_dead_stock_found(session_id, data)
    - SSE endpoint subscribes: async for event in broadcaster.subscribe(session_id)
    """
    
    CHANNEL_PREFIX = "scan_session:"
    
    def __init__(self):
        self.redis = get_redis_client()
    
    def _get_channel(self, session_id: str) -> str:
        return f"{self.CHANNEL_PREFIX}{session_id}"
    
    def publish_dead_stock_found(
        self, 
        session_id: str, 
        product: Dict[str, Any],
        running_total: Dict[str, Any]
    ):
        """
        Publish when a dead stock product is found.
        Called from quick_scan Celery task.
        """
        message = {
            "type": "dead_stock_found",
            "product": product,
            "running_total": running_total
        }
        channel = self._get_channel(session_id)
        self.redis.publish(channel, json.dumps(message))
        logger.info(f"📡 Published dead_stock_found to {channel}")
    
    def publish_scan_progress(
        self, 
        session_id: str,
        products_scanned: int,
        total_products: int
    ):
        """Publish scan progress update."""
        message = {
            "type": "scan_progress",
            "products_scanned": products_scanned,
            "total_products": total_products
        }
        self.redis.publish(self._get_channel(session_id), json.dumps(message))
    
    def publish_quick_scan_complete(
        self, 
        session_id: str,
        summary: Dict[str, Any]
    ):
        """
        Publish when quick scan (50 products) is complete.
        Includes summary and remaining products count.
        """
        message = {
            "type": "quick_scan_complete",
            "summary": summary
        }
        self.redis.publish(self._get_channel(session_id), json.dumps(message))
        logger.info(f"✅ Published quick_scan_complete to {session_id}")
    
    def publish_error(self, session_id: str, error: str):
        """Publish error event."""
        message = {
            "type": "error",
            "error": error
        }
        self.redis.publish(self._get_channel(session_id), json.dumps(message))
    
    def get_pubsub(self, session_id: str):
        """
        Get a pubsub object for subscribing to scan events.
        Used by SSE endpoint.
        """
        pubsub = self.redis.pubsub()
        pubsub.subscribe(self._get_channel(session_id))
        return pubsub


# Singleton for easy access
_broadcaster: Optional[ScanBroadcaster] = None

def get_broadcaster() -> ScanBroadcaster:
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = ScanBroadcaster()
    return _broadcaster
