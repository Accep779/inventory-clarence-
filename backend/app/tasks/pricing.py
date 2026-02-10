"""
Pricing Tasks.

Handles scheduled price updates and reversions for campaigns.
Uses Platform Adapters for execution.
"""
from celery import shared_task
import asyncio
from typing import Dict, Any

from app.database import async_session_maker
from app.models import Merchant, Product, ProductVariant
from app.adapters.registry import AdapterRegistry
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

@shared_task(name="app.tasks.pricing.revert_campaign_pricing")
def revert_campaign_pricing(merchant_id: str, platform_product_id: str, platform_variant_id: str, original_price: str):
    """
    Reverts a product's price to its original value after a campaign ends.
    """
    async def _revert():
        async with async_session_maker() as session:
            # 1. Fetch Merchant
            result = await session.execute(select(Merchant).where(Merchant.id == merchant_id))
            merchant = result.scalar_one_or_none()
            
            if not merchant:
                logger.error(f"Merchant {merchant_id} not found during price reversion")
                return

            # 2. Resolve Adapter
            try:
                adapter = AdapterRegistry.get_adapter(merchant.platform)
            except Exception as e:
                logger.error(f"Adapter resolution failed: {e}")
                return

            # 3. Execute Reversion
            try:
                from decimal import Decimal
                price_decimal = Decimal(original_price)
                
                merchant_context = merchant.platform_context or {}
                
                await adapter.update_price(
                    merchant_context=merchant_context,
                    platform_product_id=platform_product_id,
                    platform_variant_id=platform_variant_id,
                    new_price=price_decimal
                )
                logger.info(f"Reverted price for {platform_variant_id} to {original_price}")
            except Exception as e:
                logger.error(f"Price reversion failed: {e}")
                # TODO: Notify merchant or retry
    
    # Run async logic
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # Should not happen in standard celery worker, but if using gevent/asyncio pool:
        loop.create_task(_revert())
    else:
        loop.run_until_complete(_revert())
