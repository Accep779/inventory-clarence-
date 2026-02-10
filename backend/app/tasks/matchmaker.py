"""
Matchmaker Agent - Customer RFM Segmentation Engine.

This agent runs daily to:
1. Calculate RFM scores for all customers
2. Assign segments (Champions, Loyal, At-Risk, Lapsed, etc.)
3. Enable targeted audience selection for clearance campaigns
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import async_session_maker
from app.orchestration import background_task, registry
from app.models import Merchant, Customer, Order


from app.agents.matchmaker import MatchmakerAgent as ReasoningMatchmaker

class MatchmakerAgent:
    """
    Autonomous Customer Segmentation Agent.
    
    Refactored to use the World-Class Reasoning Engine.
    """
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self.reasoning_matchmaker = ReasoningMatchmaker(merchant_id)
    
    async def run_daily_segmentation(self) -> Dict[str, Any]:
        """
        Main entry point - called by Celery beat scheduler.
        """
        print(f"👥 [Matchmaker] Starting RFM analysis for merchant {self.merchant_id}")
        
        # We preserve the legacy RFM calculation for data consistency,
        # but the reasoning happens in the new agent class.
        return await self._calculate_legacy_rfm()

    async def _calculate_legacy_rfm(self) -> Dict[str, Any]:
        """Legacy RFM math for database population."""
        async with async_session_maker() as session:
            # Fetch all customers with orders
            result = await session.execute(
                select(Customer)
                .where(Customer.merchant_id == self.merchant_id)
                .options(selectinload(Customer.orders))
            )
            customers = result.scalars().all()
            
            if not customers:
                return {"status": "no_customers"}
            
            all_totals = [float(c.total_spent) for c in customers if c.total_spent]
            percentiles = self._calculate_percentiles(all_totals)
            
            segment_counts = {
                "champions": 0, "loyal": 0, "at_risk": 0, "lapsed": 0, "lost": 0, "new_customers": 0, "potential": 0,
            }
            
            for customer in customers:
                r = self._calculate_recency_score(customer)
                f = self._calculate_frequency_score(customer)
                m = self._calculate_monetary_score(customer, percentiles)
                
                segment = self._assign_segment(r, f, m)
                customer.rfm_segment = segment
                segment_counts[segment] += 1
            
            await session.commit()
            return {"status": "completed", "total_customers": len(customers), "segments": segment_counts}

    async def get_audience_for_strategy(self, strategy: str) -> List[str]:
        """
        Reason about which customers actually want this strategy.
        Now delegated to the high-intelligence agent.
        """
        # We use a dummy product context if none provided for generic queries
        # (Though usually called from StrategyAgent which now passes product)
        matching = await self.reasoning_matchmaker.get_optimal_audience(
            product_data={"title": "Generic Product"},
            strategy=strategy,
            session=None # Session handles separately in agent
        )
        return matching["target_segments"]
    
    def _calculate_recency_score(self, customer: Customer) -> int:
        """
        Score 1-5 based on days since last order.
        
        5: <= 30 days
        4: 31-60 days
        3: 61-90 days
        2: 91-180 days
        1: > 180 days
        """
        if not customer.last_order_date:
            return 1
        
        days_ago = (datetime.utcnow() - customer.last_order_date).days
        
        if days_ago <= 30:
            return 5
        elif days_ago <= 60:
            return 4
        elif days_ago <= 90:
            return 3
        elif days_ago <= 180:
            return 2
        else:
            return 1
    
    def _calculate_frequency_score(self, customer: Customer) -> int:
        """
        Score 1-5 based on total order count.
        
        5: 10+ orders
        4: 5-9 orders
        3: 3-4 orders
        2: 2 orders
        1: 1 order
        """
        orders = customer.total_orders or 0
        
        if orders >= 10:
            return 5
        elif orders >= 5:
            return 4
        elif orders >= 3:
            return 3
        elif orders >= 2:
            return 2
        else:
            return 1
    
    def _calculate_monetary_score(self, customer: Customer, percentiles: Dict[int, float]) -> int:
        """
        Score 1-5 based on total spent (percentile-based).
        
        5: Top 20%
        4: 60-80%
        3: 40-60%
        2: 20-40%
        1: Bottom 20%
        """
        total_spent = float(customer.total_spent or 0)
        
        if total_spent >= percentiles.get(80, 1000):
            return 5
        elif total_spent >= percentiles.get(60, 500):
            return 4
        elif total_spent >= percentiles.get(40, 250):
            return 3
        elif total_spent >= percentiles.get(20, 100):
            return 2
        else:
            return 1
    
    def _calculate_percentiles(self, values: List[float]) -> Dict[int, float]:
        """Calculate percentile thresholds."""
        if not values:
            return {20: 100, 40: 250, 60: 500, 80: 1000}
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        return {
            20: sorted_values[int(n * 0.20)] if n > 5 else 100,
            40: sorted_values[int(n * 0.40)] if n > 5 else 250,
            60: sorted_values[int(n * 0.60)] if n > 5 else 500,
            80: sorted_values[int(n * 0.80)] if n > 5 else 1000,
        }
    
    def _assign_segment(self, r: int, f: int, m: int) -> str:
        """
        Assign customer segment based on RFM scores.
        
        Segments:
        - champions: High R, F, M (best customers)
        - loyal: Regular buyers
        - at_risk: Good customers going quiet
        - lapsed: Haven't bought in a while
        - lost: Inactive for 180+ days
        - new_customers: Recent first purchase
        - potential: Everyone else
        """
        # Champions: Best customers (recent, frequent, high-value)
        if r >= 4 and f >= 4 and m >= 4:
            return "champions"
        
        # Loyal: Regular buyers with decent recency
        if r >= 3 and f >= 3:
            return "loyal"
        
        # At Risk: Were valuable but going quiet
        if r <= 2 and f >= 3 and m >= 3:
            return "at_risk"
        
        # Lapsed: Haven't bought recently but have history
        if r == 1 and f >= 2:
            return "lapsed"
        
        # New: Recent first purchase
        if r >= 4 and f == 1:
            return "new_customers"
        
        # Lost: Inactive for long time
        if r == 1 and f == 1:
            return "lost"
        
        # Potential: Everyone else
        return "potential"
    
    async def get_audience_for_strategy(self, strategy: str) -> List[str]:
        """
        Get target customer segments for a given clearance strategy.
        
        Returns list of RFM segments to target.
        """
        strategy_audiences = {
            "progressive_discount": ["loyal", "at_risk"],
            "flash_sale": ["champions", "loyal", "at_risk"],
            "bundle_promotion": ["champions", "loyal"],
            "loyalty_exclusive": ["champions"],
            "aggressive_liquidation": ["lapsed", "lost", "potential"],
        }
        
        return strategy_audiences.get(strategy, ["loyal", "at_risk"])


# ============================================================================
# CELERY TASKS
# ============================================================================

@celery_app.task(name="app.tasks.matchmaker.run_daily_segmentation_all_merchants")
def run_daily_segmentation_all_merchants():
    """
    AUTONOMOUS: Daily cron job dispatcher.
    Uses FAN-OUT pattern for parallel segmentation.
    """
    asyncio.run(_dispatch_merchant_tasks())


async def _dispatch_merchant_tasks():
    """Dispatch individual merchant tasks for parallel processing."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Merchant.id).where(Merchant.is_active == True)
        )
        merchant_ids = [row[0] for row in result.all()]
    
    print(f"🚀 [Matchmaker] Dispatching segmentation for {len(merchant_ids)} merchants")
    
    # Fan-out to worker pool
    from celery import group
    job = group(
        run_segmentation_for_merchant.s(mid) 
        for mid in merchant_ids
    )
    job.apply_async()


@celery_app.task(
    name="app.tasks.matchmaker.run_segmentation_for_merchant",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
    queue='batch',
    rate_limit='100/m'
)
def run_segmentation_for_merchant(self, merchant_id: str):
    """Run segmentation for a specific merchant with auto-retry."""
    asyncio.run(_run_segmentation_single(merchant_id))


async def _run_segmentation_single(merchant_id: str):
    """Async implementation for single merchant."""
    agent = MatchmakerAgent(merchant_id)
    return await agent.run_daily_segmentation()
