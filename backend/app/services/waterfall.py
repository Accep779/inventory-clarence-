# app/services/waterfall.py
"""
Waterfall Service
=================
Implements a drip-feed mechanism for high-volume communications.
Prevents API throttling and protects sender reputation.

EXTRACTED FROM: Cephly architecture
"""

import asyncio
import logging
from typing import List, Any, Callable

logger = logging.getLogger(__name__)

class WaterfallService:
    """
    Manages staggered batch execution.
    """
    
    def __init__(self, batch_size: int = 20, delay_seconds: int = 120):
        self.batch_size = batch_size
        self.delay_seconds = delay_seconds

    async def execute_waterfall(self, items: List[Any], dispatch_func: Callable[[Any], Any]):
        """
        Executes a waterfall send in batches.
        """
        total = len(items)
        logger.info(f"🌊 Starting Waterfall for {total} items. Batch size: {self.batch_size}")
        
        for i in range(0, total, self.batch_size):
            batch = items[i : i + self.batch_size]
            
            # Execute batch concurrently
            tasks = [dispatch_func(item) for item in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            if i + self.batch_size < total:
                logger.debug(f"⏳ Sleeping {self.delay_seconds}s before next batch...")
                await asyncio.sleep(self.delay_seconds)
                
        logger.info("✅ Waterfall execution complete.")
