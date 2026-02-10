"""
Proactive Scan Engine
=====================
[ENGINE #5]: The System Loop.
Monitors product state and "Wakes Up" the Strategy brain when critical
deltas are detected (e.g., inventory velocity drops).
"""

import logging
from typing import List
from sqlalchemy import select
from app.database import async_session_maker
from app.models import Product, Merchant

logger = logging.getLogger(__name__)

class ProactiveScanService:
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id

    async def scan_for_triggers(self):
        """
        Scans all products for 'Critical' or 'Severe' dead stock signals.
        If found, it 'Wakes Up' the Observer Agent.
        """
        async with async_session_maker() as session:
            # 1. Fetch products with severe/critical status or high inventory
            # (Note: In a real system, this would use a complex velocity SQL query)
            stmt = select(Product).where(
                Product.merchant_id == self.merchant_id,
                Product.total_inventory > 50 # Example trigger: High inventory
            )
            result = await session.execute(stmt)
            products = result.scalars().all()
            
            triggered_count = 0
            for product in products:
                # 2. Evaluate Trigger: Velocity Drop
                # If product hasn't sold in 30 days, trigger a scan
                if not product.last_sale_date or (product.updated_at - product.last_sale_date).days > 30:
                    logger.info(f"🚨 [Proactive] Velocity drop detected for {product.title}. Triggering Observer.")
                    
                    # 3. Wake Up Observer Agent
                    from app.agents.observer import ObserverAgent
                    observer = ObserverAgent(self.merchant_id)
                    # We run this in the background (fire and forget for the scan)
                    import asyncio
                    asyncio.create_task(observer.scan_dead_stock())
                    triggered_count += 1
            
            return triggered_count
