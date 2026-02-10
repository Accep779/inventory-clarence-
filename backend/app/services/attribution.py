# app/services/attribution.py
"""
Attribution Service
===================
Calculates ROI and attributes revenue to specific agent actions.

EXTRACTED FROM: Cephly architecture
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal
from sqlalchemy import select, func
from app.database import async_session_maker
from app.models import InboxItem, Ledger, Merchant, Order

logger = logging.getLogger(__name__)

class AttributionService:
    """
    Manages financial attribution logic.
    """
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id

    async def sync_ledger(self):
        """
        De-duplicates revenue and updates the financial ledger.
        [THE HIGHLANDER RULE]: Only one action can claim an order.
        """
        async with async_session_maker() as session:
            # 1. Fetch attributed candidate orders
            # (In Multi, we'll look for orders with discount codes from proposals)
            proposals_result = await session.execute(
                select(InboxItem).where(
                    InboxItem.merchant_id == self.merchant_id,
                    InboxItem.status == 'executed'
                )
            )
            proposals = proposals_result.scalars().all()
            
            # Map of discount_code -> proposal
            code_map = {}
            for p in proposals:
                # Assuming copy generation stored a code or we can match by product
                data = p.proposal_data
                # For demo, we match by product_id if price drop, or code if flash sale
                code = data.get('copy', {}).get('discount_code')
                if code:
                    code_map[code] = p

            # 2. Fetch recent orders
            orders_result = await session.execute(
                select(Order).where(
                    Order.merchant_id == self.merchant_id,
                    Order.created_at >= datetime.utcnow() - timedelta(days=30)
                )
            )
            orders = orders_result.scalars().all()

            new_ledger_entries = []
            for order in orders:
                # Check if already in ledger
                existing = await session.execute(
                    select(Ledger).where(Ledger.order_id == str(order.shopify_order_id))
                )
                if existing.scalar_one_or_none():
                    continue

                # [ENGINE #7]: World-Class Attribution Matching
                # Match by line items against promoted products
                from app.models import OrderItem
                from sqlalchemy.orm import selectinload
                items_stmt = select(OrderItem).where(OrderItem.order_id == order.id).options(selectinload(OrderItem.product))
                line_items = (await session.execute(items_stmt)).scalars().all()
                
                is_attributed = False
                source = "Direct"
                
                for item in line_items:
                    # Check if this product was promoted in an executed proposal
                    promoted_stmt = select(InboxItem).where(
                        InboxItem.merchant_id == self.merchant_id,
                        InboxItem.status == 'executed',
                        InboxItem.product_id == item.product_id
                    ).limit(1)
                    promo = (await session.execute(promoted_stmt)).scalar_one_or_none()
                    
                    if promo:
                        is_attributed = True
                        source = f"Agent ({promo.agent_type})"
                        break
                
                if is_attributed:
                    # [FINTECH FIX]: Calculate Total Cost for Net Margin Attribution
                    total_order_cost = Decimal("0.00")
                    for item in line_items:
                        # Fetch item cost (fallback to 0 if missing - merchant takes hit, we don't profit)
                        if item.product and item.product.cost_per_unit:
                            total_order_cost += item.product.cost_per_unit * item.quantity
                    
                    # Recovered Margin = Total Price - Total COGS
                    recovered_margin = order.total_price - total_order_cost
                    
                    # [INCENTIVE ALIGNMENT]: 25% of Recovered Margin, 0 if loss.
                    # This ensures Cephly only profits if the merchant profits.
                    agent_stake = max(Decimal("0.00"), recovered_margin * Decimal("0.25"))

                    entry = Ledger(
                        merchant_id=self.merchant_id,
                        order_id=str(order.shopify_order_id),
                        gross_amount=order.total_price,
                        net_amount=order.total_price - total_order_cost, # Store actual profit
                        agent_stake=agent_stake,
                        attribution_source=source,
                        created_at=order.created_at
                    )
                    new_ledger_entries.append(entry)
                    
                    # Also update Journey progress if applicable
                    from app.services.journey_engine import JourneyService
                    journey_service = JourneyService(self.merchant_id)
                    await journey_service.update_progress()

            if new_ledger_entries:
                session.add_all(new_ledger_entries)
                await session.commit()
                logger.info(f"✅ Attributed {len(new_ledger_entries)} orders to ledger")

    async def get_roi_stats(self) -> dict:
        """
        Returns high-level ROI stats for the dashboard.
        """
        async with async_session_maker() as session:
            # Sum attributed gross revenue
            revenue_result = await session.execute(
                select(func.sum(Ledger.gross_amount))
                .where(Ledger.merchant_id == self.merchant_id)
            )
            total_revenue = revenue_result.scalar() or Decimal("0.00")
            
            # Sum attributed recovered margin (net_amount in Ledger)
            margin_result = await session.execute(
                select(func.sum(Ledger.net_amount))
                .where(Ledger.merchant_id == self.merchant_id)
            )
            total_margin = margin_result.scalar() or Decimal("0.00")

            # Sum agent stake (what we actually earned)
            stake_result = await session.execute(
                select(func.sum(Ledger.agent_stake))
                .where(Ledger.merchant_id == self.merchant_id)
            )
            total_stake = stake_result.scalar() or Decimal("0.00")
            
            # Sum LLM costs
            from app.models import LLMUsageLog
            cost_result = await session.execute(
                select(func.sum(LLMUsageLog.cost_usd))
                .where(LLMUsageLog.merchant_id == self.merchant_id)
            )
            total_llm_cost = cost_result.scalar() or Decimal("0.01")  # Floor
            
            # ROI = Total Revenue / Total LLM Cost
            roi = total_revenue / total_llm_cost if total_llm_cost > 0 else 0
            
            return {
                "total_recovered_revenue": float(total_revenue),
                "total_recovered_margin": float(total_margin),
                "total_agent_earnings": float(total_stake),
                "total_llm_cost": float(total_llm_cost),
                "roi_multiplier": round(float(roi), 2)
            }
