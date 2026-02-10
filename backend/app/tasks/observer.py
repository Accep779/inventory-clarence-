"""
Observer Agent - Dead Stock Detection Engine.

This is the CORE AUTONOMOUS AGENT that runs daily to:
1. Analyze all products for sales velocity
2. Classify dead stock by severity
3. Create inbox proposals for critical items

The Observer Agent is the "Eyes" of the system.
"""

import asyncio
from uuid import uuid4
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

# NOTE: Celery removed. This is now a direct async class. Migrate to Temporal activity.
from app.database import async_session_maker
from app.models import Merchant, Product, OrderItem, InboxItem
# from app.services.thought_logger import ThoughtLogger # Removed direct dependency


from app.agents.observer import ObserverAgent as ReasoningObserver
from app.agents.strategy import StrategyAgent

class ObserverAgent:
    """
    Autonomous Dead Stock Detection Agent.
    
    Refactored to use the World-Class Reasoning Engine.
    """
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self.reasoning_observer = ReasoningObserver(merchant_id)
        self.strategy_agent = StrategyAgent(merchant_id)
        
    async def run_daily_analysis(self) -> Dict[str, Any]:
        """
        Main entry point - called by Celery beat scheduler or worker.
        Optimized for 10K+ products: Batching + Eager Loading + Clustering.
        """
        print(f"🔍 [Observer] Starting analysis for merchant {self.merchant_id}")
        
        execution_id = str(uuid4())
        # [SECURE REFACTOR] Use Agent API for logging
        await self.reasoning_observer._log_thought(
             thought_type="analysis",
             summary="Starting daily inventory reasoning scan...",
             detailed_reasoning={"engine": "AI Reasoning + Memory", "mode": "batch_optimized"},
             execution_id=execution_id,
             step_number=1
        )
        
        async with async_session_maker() as session:
            BATCH_SIZE = 500
            offset = 0
            total_processed = 0
            dead_stock_count = 0
            
            while True:
                # 1. Batch fetch with Eager Loading (Fixes N+1)
                result = await session.execute(
                    select(Product)
                    .where(Product.merchant_id == self.merchant_id, Product.status == "active")
                    .options(selectinload(Product.variants))
                    .limit(BATCH_SIZE)
                    .offset(offset)
                )
                products = result.scalars().all()
                if not products:
                    break
                
                # 2. Convert to dicts for Cluster Analysis
                product_dicts = []
                for p in products:
                    product_dicts.append({
                        "id": p.id,
                        "title": p.title,
                        "product_type": p.product_type,
                        # Safely access eager-loaded variants
                        "variants": [{"price": str(p.variants[0].price), "inventory_quantity": p.total_inventory}] if p.variants else [],
                        "days_since_last_sale": (datetime.utcnow() - p.last_sale_date).days if p.last_sale_date else 999,
                        "units_sold_30d": p.units_sold_30d or 0,
                        "created_at": p.created_at.isoformat() if p.created_at else None
                    })
                
                # 3. Bulk Observation (Clustering) - Reduces LLM Calls
                bulk_analysis = await self.reasoning_observer.observe_inventory(product_dicts, session)
                
                # 4. Map results back to DB objects (for Strategy/Logging only - NOT for persistence)
                analysis_map_by_id = {res['id']: res for res in bulk_analysis if 'id' in res}

                # PUSH OBSERVATIONS TO API
                # This replaces the direct DB flush below
                try:
                    await self.reasoning_observer.batch_update_status(bulk_analysis)
                except Exception as e:
                    print(f"❌ [Observer] Failed to push updates to API: {e}")

                # 5. Trigger Strategy Agent for critical items
                # We still loop to trigger Strategy, but looking at the READ-ONLY state or the analysis result
                for product in products:
                    if product.id not in analysis_map_by_id:
                        continue
                        
                    analysis = analysis_map_by_id[product.id]
                    
                    if analysis["is_dead_stock"]:
                        dead_stock_count += 1
                        
                    # Auto-propose for critical items
                    if analysis["severity"] in ("critical", "high"):
                        try:
                            # Trigger Strategy
                            await self.strategy_agent.plan_clearance(product.id)
                        except Exception as e:
                            pass

                # No session.flush() needed for product updates anymore!
                total_processed += len(products)
                offset += BATCH_SIZE
                
                # Release memory
                del products, product_dicts, bulk_analysis
            
            await session.commit() # Commit needed only if Strategy Agent or Logging did something implicit (though Strategy uses its own logic usually)
            
            return {
                "status": "completed",
                "total_products": total_processed,
                "dead_stock_count": dead_stock_count
            }


# ============================================================================
# CELERY TASKS
# ============================================================================

@celery_app.task(name="app.tasks.observer.run_daily_analysis_all_merchants")
def run_daily_analysis_all_merchants():
    """
    AUTONOMOUS: Daily cron job dispatcher.
    Uses FAN-OUT pattern to parallelize merchant analysis.
    """
    asyncio.run(_dispatch_merchant_tasks())


async def _dispatch_merchant_tasks():
    """Dispatch individual merchant tasks for parallel processing."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Merchant.id).where(Merchant.is_active == True)
        )
        merchant_ids = [row[0] for row in result.all()]
    
    print(f"🚀 [Observer] Dispatching analysis for {len(merchant_ids)} merchants")
    
    # Fan-out to worker pool
    from celery import group
    # Use .s() signature for defining tasks
    job = group(
        run_analysis_for_merchant.s(mid) 
        for mid in merchant_ids
    )
    job.apply_async()


@celery_app.task(
    name="app.tasks.observer.run_analysis_for_merchant",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
    queue='batch', # Force to batch queue
    rate_limit='50/m' # Prevent database overload
)
def run_analysis_for_merchant(self, merchant_id: str):
    """Run analysis for a specific merchant."""
    asyncio.run(_run_analysis_single(merchant_id))


async def _run_analysis_single(merchant_id: str):
    """Async implementation for single merchant."""
    agent = ObserverAgent(merchant_id)
    return await agent.run_daily_analysis()

@celery_app.task(
    name="app.tasks.observer.run_analysis_for_product",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
    queue='realtime', # High priority queue
    rate_limit='100/m'
)
def run_analysis_for_product(self, merchant_id: str, product_id: str):
    """Real-time analysis for a single product triggered by webhook."""
    asyncio.run(_run_analysis_product(merchant_id, product_id))

async def _run_analysis_product(merchant_id: str, product_id: str):
    """Async implementation for single product."""
    from app.services.thought_logger import ThoughtLogger
    
    # 1. Fetch Product
    async with async_session_maker() as session:
        result = await session.execute(
            select(Product)
            .where(Product.id == product_id, Product.merchant_id == merchant_id)
            .options(selectinload(Product.variants))
        )
        product = result.scalar_one_or_none()
        if not product:
            return
        
        # 2. Convert to dict for Agent
        p_data = {
            "id": product.id,
            "title": product.title,
            "product_type": product.product_type,
            "variants": [{"price": str(product.variants[0].price), "inventory_quantity": product.total_inventory}] if product.variants else [],
            "days_since_last_sale": (datetime.utcnow() - product.last_sale_date).days if product.last_sale_date else 999,
            "units_sold_30d": product.units_sold_30d or 0,
            "created_at": product.created_at.isoformat() if product.created_at else None
        }
        
    # 3. Analyze (ObserverAgent Logic)
    agent = ObserverAgent(merchant_id)
    
    # Log Start
    await agent.reasoning_observer._log_thought(
        thought_type="trigger",
        summary=f"⚡ Real-time analysis trigger for '{p_data['title']}'",
        execution_id=str(uuid4())
    )
    
    async with async_session_maker() as session:
        analysis = await agent.reasoning_observer.observe_product(p_data, session)
        
        # 4. Push update via API
        await agent.reasoning_observer.batch_update_status([analysis])
        
        # 5. Trigger Strategy if needed (Critical only)
        if analysis["severity"] in ("critical", "high") and analysis["is_dead_stock"]:
             await agent.strategy_agent.plan_clearance(product_id)
