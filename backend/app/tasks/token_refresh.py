"""
Token Refresh Celery Tasks
==========================

Periodic tasks for proactive token refresh.
Run via Celery Beat every 15 minutes.
"""

import logging
from celery import shared_task
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@shared_task(name="refresh_expiring_tokens")
def refresh_expiring_tokens():
    """
    Periodic task to refresh tokens expiring in the next hour.
    
    This task is designed to run every 15 minutes via Celery Beat.
    It proactively refreshes tokens before they expire to ensure
    uninterrupted agent operations.
    """
    import asyncio
    asyncio.run(_refresh_expiring_tokens_async())


async def _refresh_expiring_tokens_async():
    """Async implementation of token refresh."""
    from app.services.token_vault import TokenVaultService, get_expiring_tokens
    
    logger.info("🔄 Starting token refresh sweep...")
    
    try:
        expiring_tokens = await get_expiring_tokens(hours_until_expiry=1)
        
        if not expiring_tokens:
            logger.info("✅ No tokens expiring in the next hour")
            return {"refreshed": 0, "failed": 0}
        
        logger.info(f"Found {len(expiring_tokens)} tokens expiring soon")
        
        refreshed = 0
        failed = 0
        
        for token in expiring_tokens:
            try:
                vault = TokenVaultService(token.merchant_id)
                new_token = await vault.get_access_token(token.provider)
                
                if new_token:
                    refreshed += 1
                    logger.info(f"✅ Refreshed {token.provider} token for {token.merchant_id}")
                else:
                    failed += 1
                    logger.warning(f"❌ Failed to refresh {token.provider} token for {token.merchant_id}")
                    
            except Exception as e:
                failed += 1
                logger.error(f"❌ Error refreshing token: {e}")
        
        logger.info(f"🔄 Token refresh complete: {refreshed} refreshed, {failed} failed")
        return {"refreshed": refreshed, "failed": failed}
        
    except Exception as e:
        logger.error(f"Token refresh sweep failed: {e}")
        return {"error": str(e)}


@shared_task(name="check_token_health")
def check_token_health():
    """
    Periodic task to check overall token health across all merchants.
    Run daily for monitoring and alerting.
    """
    import asyncio
    return asyncio.run(_check_token_health_async())


async def _check_token_health_async():
    """Async implementation of health check."""
    from sqlalchemy import select, func
    from app.database import async_session_maker
    from app.models import TokenVault
    
    async with async_session_maker() as session:
        # Count tokens by status
        result = await session.execute(
            select(
                TokenVault.status,
                func.count(TokenVault.id)
            ).group_by(TokenVault.status)
        )
        
        status_counts = {row[0]: row[1] for row in result.all()}
        
        logger.info(f"📊 Token Health Report: {status_counts}")
        
        # Alert if too many errors
        error_count = status_counts.get("error", 0)
        if error_count > 5:
            logger.warning(f"⚠️ High token error count: {error_count} tokens in error state")
        
        return status_counts
