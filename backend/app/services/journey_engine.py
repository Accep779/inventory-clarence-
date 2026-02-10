"""
Journey Service
===============
[ENGINE #3]: Commercial Journeys.
Coordinates long-term goals and state transitions.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from decimal import Decimal
from sqlalchemy import select, func
from app.database import async_session_maker
from app.models import MerchantJourney

logger = logging.getLogger(__name__)

class JourneyService:
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id

    async def create_liquidation_sprint(self, target_revenue: float, days: int = 30):
        """
        Creates a new SMART goal journey.
        """
        async with async_session_maker() as session:
            journey = MerchantJourney(
                merchant_id=self.merchant_id,
                title=f"Liquidate ${target_revenue:,.0f} in {days} Days",
                journey_type="liquidation_sprint",
                target_metric="revenue",
                target_value=Decimal(str(target_revenue)),
                deadline_at=datetime.utcnow() + timedelta(days=days)
            )
            session.add(journey)
            await session.commit()
            return journey

    async def update_progress(self):
        """
        Aggregates revenue from Ledger and updates journey progress.
        """
        from app.models import Ledger
        async with async_session_maker() as session:
            # 1. Fetch active journeys
            stmt = select(MerchantJourney).where(
                MerchantJourney.merchant_id == self.merchant_id,
                MerchantJourney.status == 'active'
            )
            result = await session.execute(stmt)
            journeys = result.scalars().all()
            
            for journey in journeys:
                # 2. Sum attributed revenue since journey start
                rev_stmt = select(func.sum(Ledger.gross_amount)).where(
                    Ledger.merchant_id == self.merchant_id,
                    Ledger.created_at >= journey.created_at
                )
                rev_res = await session.execute(rev_stmt)
                total_rev = rev_res.scalar() or Decimal("0.00")
                
                journey.current_value = total_rev
                
                # 3. Check for completion
                if journey.current_value >= journey.target_value:
                    journey.status = 'completed'
                    logger.info(f"🏆 Journey Completed: {journey.title}")
                elif datetime.utcnow() > journey.deadline_at:
                    journey.status = 'failed'
                    logger.info(f"🛑 Journey Expired: {journey.title}")
            
            await session.commit()
