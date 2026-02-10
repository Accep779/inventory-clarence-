"""
Reactivation Task
================

Autonomous daily task for identifying dormant customers and processing
reactivation journeys.

MIGRATED: From Celery to Temporal/orchestration.
"""

import asyncio
from app.database import async_session_maker
from app.orchestration import background_task, registry
from app.models import Merchant
from app.agents.reactivation import ReactivationAgent
from sqlalchemy import select


@background_task(name="run_daily_reactivation_all_merchants", queue="reactivation")
async def run_daily_reactivation_all_merchants():
    """
    AUTONOMOUS: Daily cron job dispatcher.
    Uses FAN-OUT pattern for parallel reactivation reasoning.
    """
    await _dispatch_merchant_tasks()


async def _dispatch_merchant_tasks():
    """Dispatch individual merchant tasks for parallel processing."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Merchant.id).where(Merchant.is_active == True)
        )
        merchant_ids = [row[0] for row in result.all()]

    print(f"🚀 [Reactivation] Dispatching journeys for {len(merchant_ids)} merchants")

    # Fan-out using asyncio (replace with Temporal fan-out for production)
    tasks = [
        run_reactivation_for_merchant(mid)
        for mid in merchant_ids
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


@background_task(name="run_reactivation_for_merchant", queue="reactivation")
async def run_reactivation_for_merchant(merchant_id: str):
    """Run reactivation logic for a specific merchant."""
    await _run_reactivation_single(merchant_id)


async def _run_reactivation_single(merchant_id: str):
    """Execute reactivation agent for one merchant."""
    try:
        agent = ReactivationAgent(merchant_id)
        # 1. Scan for new candidates
        await agent.scan_for_dormant_customers()
        # 2. Step existing journeys
        await agent.step_journeys()
    except Exception as e:
        print(f"❌ [Reactivation] Error for merchant {merchant_id}: {e}")
        raise e


# Register tasks
registry.register_background_task(run_daily_reactivation_all_merchants)
registry.register_background_task(run_reactivation_for_merchant)
