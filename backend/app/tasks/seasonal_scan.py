# backend/app/tasks/seasonal_scan.py
"""
Seasonal Scan Task
==================

Celery task that runs the SeasonalTransitionAgent to identify
at-risk seasonal products and generate clearance proposals.

Implements SSE broadcasting for real-time progress updates.
"""

import logging
from datetime import datetime
from typing import Optional

from celery import shared_task
from sqlalchemy import select

from app.database import sync_session_maker, async_session_maker
from app.models import Merchant
from app.agents.seasonal_transition import SeasonalTransitionAgent
from app.services.thought_logger import ThoughtLogger

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def run_seasonal_scan_for_merchant(self, merchant_id: str):
    """
    Run seasonal risk scan for a single merchant.
    
    This is the Celery entry point - wraps async execution.
    """
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            _run_seasonal_scan_async(merchant_id)
        )
        return result
    except Exception as e:
        logger.error(f"Seasonal scan failed for {merchant_id}: {e}")
        self.retry(exc=e, countdown=60)


async def _run_seasonal_scan_async(merchant_id: str) -> dict:
    """
    Async implementation of seasonal scan.
    """
    from app.services.scan_broadcaster import ScanBroadcaster
    
    broadcaster = ScanBroadcaster(merchant_id)
    agent = SeasonalTransitionAgent(merchant_id)
    
    # Broadcast start
    await broadcaster.broadcast({
        'type': 'scan_started',
        'agent': 'seasonal',
        'timestamp': datetime.utcnow().isoformat()
    })
    
    try:
        # Progress callback for SSE
        async def progress_callback(data):
            await broadcaster.broadcast({
                'type': 'scan_progress',
                'agent': 'seasonal',
                **data
            })
        
        # Scan for risks
        risks = await agent.scan_seasonal_risks(progress_callback)
        
        # Process each at-risk product
        proposals_created = 0
        for risk_item in risks:
            try:
                product = risk_item['product']
                risk = risk_item['risk']
                
                # Skip low risk
                if risk.risk_level == 'low':
                    continue
                
                # Generate proposal
                result = await agent.plan_seasonal_clearance(product.id, risk)
                
                if result['status'] == 'success':
                    proposals_created += 1
                    
                    await broadcaster.broadcast({
                        'type': 'proposal_created',
                        'agent': 'seasonal',
                        'product_title': product.title,
                        'strategy': result['strategy'],
                        'risk_level': risk.risk_level
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to process product {product.id}: {e}")
                continue
        
        # Broadcast completion
        await broadcaster.broadcast({
            'type': 'scan_completed',
            'agent': 'seasonal',
            'risks_found': len(risks),
            'proposals_created': proposals_created,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        return {
            'status': 'success',
            'risks_found': len(risks),
            'proposals_created': proposals_created
        }
        
    except Exception as e:
        await broadcaster.broadcast({
            'type': 'scan_failed',
            'agent': 'seasonal',
            'error': str(e)
        })
        raise


@shared_task
def run_weekly_seasonal_scan():
    """
    Weekly scheduled task to scan all merchants.
    
    Add to Celery beat schedule:
    'weekly-seasonal-scan': {
        'task': 'app.tasks.seasonal_scan.run_weekly_seasonal_scan',
        'schedule': crontab(day_of_week='sunday', hour=2, minute=0)
    }
    """
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(_run_all_merchants_scan())


async def _run_all_merchants_scan():
    """Scan all active merchants."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Merchant)
            .where(Merchant.subscription_status == 'active')
        )
        merchants = result.scalars().all()
        
        logger.info(f"Starting weekly seasonal scan for {len(merchants)} merchants")
        
        for merchant in merchants:
            try:
                # Queue individual merchant scan
                run_seasonal_scan_for_merchant.delay(merchant.id)
            except Exception as e:
                logger.error(f"Failed to queue scan for {merchant.id}: {e}")
