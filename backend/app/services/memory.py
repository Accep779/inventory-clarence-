# app/services/memory.py
"""
Memory Service
==============
Provides Episodic and Semantic memory for agents, enabling them to recall
past outcomes and adapt their behavior.

This is the cognitive foundation that transforms scripts into agents.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from decimal import Decimal

from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.database import async_session_maker
from app.models import Campaign, Merchant, StoreDNA, AgentThought, TouchLog

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Agent Memory System.
    
    Provides two types of memory:
    - Episodic: "What happened?" (past campaign outcomes)
    - Semantic: "What do we know?" (merchant preferences, brand DNA)
    """
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id

    # =========================================================================
    # EPISODIC MEMORY: Recall past events and outcomes
    # =========================================================================

    async def recall_campaign_outcomes(
        self, 
        product_id: Optional[str] = None, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Recalls past campaign results, optionally filtered by product.
        
        Returns a list of outcomes with:
        - strategy_used
        - status (completed, failed)
        - performance metrics (open_rate, click_rate if available)
        - lessons (why it failed, if applicable)
        """
        async with async_session_maker() as session:
            query = (
                select(Campaign)
                .where(Campaign.merchant_id == self.merchant_id)
                .where(Campaign.status.in_(['completed', 'failed', 'active']))
                .order_by(desc(Campaign.created_at))
                .limit(limit)
            )
            
            # Filter by product if specified
            if product_id:
                # product_ids is a JSON array, we check containment
                query = query.where(Campaign.product_ids.contains([product_id]))
            
            result = await session.execute(query)
            campaigns = result.scalars().all()
            
            outcomes = []
            for campaign in campaigns:
                # Calculate performance metrics
                emails_sent = campaign.emails_sent or 1  # Avoid division by zero
                open_rate = (campaign.emails_opened or 0) / emails_sent if emails_sent > 0 else 0
                click_rate = (campaign.emails_clicked or 0) / emails_sent if emails_sent > 0 else 0
                
                outcome = {
                    'campaign_id': campaign.id,
                    'strategy': campaign.type,
                    'status': campaign.status,
                    'created_at': campaign.created_at.isoformat() if campaign.created_at else None,
                    'metrics': {
                        'emails_sent': emails_sent,
                        'open_rate': round(open_rate * 100, 1),
                        'click_rate': round(click_rate * 100, 1),
                    },
                    'success': campaign.status == 'completed' and open_rate > 0.15,  # >15% open = success
                    'copy_used': campaign.content_snapshot or {},  # The specific language that worked
                }
                
                # Add failure reason if present
                if campaign.status == 'failed':
                    outcome['failure_reason'] = 'Campaign did not achieve target engagement'
                
                outcomes.append(outcome)
            
            logger.info(f"🧠 Memory: Recalled {len(outcomes)} past outcomes for merchant {self.merchant_id}")
            return outcomes

    async def record_outcome(
        self,
        campaign_id: str,
        product_id: Optional[str],
        event_type: str,
        strategy_used: str
    ):
        """
        Records a campaign outcome event into memory.
        Called by webhooks_analytics when events are received.
        """
        # This is primarily handled by the Campaign model updates,
        # but we log an AgentThought for explicit memory trace
        from app.services.thought_logger import ThoughtLogger
        
        await ThoughtLogger.log_thought(
            merchant_id=self.merchant_id,
            agent_type="memory",
            thought_type="observation",
            summary=f"Campaign {campaign_id} received {event_type} event.",
            detailed_reasoning={
                'campaign_id': campaign_id,
                'product_id': product_id,
                'event_type': event_type,
                'strategy_used': strategy_used,
                'recorded_at': datetime.utcnow().isoformat()
            }
        )

    # =========================================================================
    # SEMANTIC MEMORY: Recall merchant identity and preferences
    # =========================================================================

    async def get_merchant_preferences(self) -> Dict[str, Any]:
        """
        Retrieves merchant's brand DNA and strategic preferences.
        
        Returns:
        - brand_tone: How the merchant communicates
        - industry_type: What sector they're in
        - max_auto_discount: Their risk tolerance
        - preferred_strategies: Explicit strategy preferences (if any)
        """
        async with async_session_maker() as session:
            # Fetch Merchant
            merchant_result = await session.execute(
                select(Merchant).where(Merchant.id == self.merchant_id)
            )
            merchant = merchant_result.scalar_one_or_none()
            
            if not merchant:
                return self._default_preferences()
            
            # Fetch StoreDNA
            dna_result = await session.execute(
                select(StoreDNA).where(StoreDNA.merchant_id == self.merchant_id)
            )
            dna = dna_result.scalar_one_or_none()
            
            preferences = {
                'brand_tone': dna.brand_tone if dna else 'professional',
                'industry_type': dna.industry_type if dna else 'general_retail',
                'max_auto_discount': float(merchant.max_auto_discount) if merchant.max_auto_discount else 0.25,
                'autonomy_enabled': merchant.governor_aggressive_mode if merchant else False,
                'store_name': merchant.store_name,
            }
            
            # Check for explicit strategy preferences in DNA (stored in brand_values)
            if dna and dna.brand_values:
                preferences['preferred_strategies'] = dna.brand_values
                preferences['avoided_strategies'] = []
            else:
                preferences['preferred_strategies'] = []
                preferences['avoided_strategies'] = []
            
            logger.info(f"🧠 Memory: Retrieved preferences for {merchant.store_name}")
            return preferences

    def _default_preferences(self) -> Dict[str, Any]:
        """Returns default preferences when merchant data is unavailable."""
        return {
            'brand_tone': 'professional',
            'industry_type': 'general_retail',
            'max_auto_discount': 0.25,
            'autonomy_enabled': False,
            'shop_name': 'Unknown',
            'preferred_strategies': [],
            'avoided_strategies': [],
        }

    # =========================================================================
    # THOUGHT RECALL: Remember past reasoning
    # =========================================================================

    async def recall_thoughts(
        self,
        agent_type: Optional[str] = None,
        product_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieves past agent thoughts for context injection.
        
        Enables agents to remember their previous reasoning about
        specific products or situations.
        """
        async with async_session_maker() as session:
            query = (
                select(AgentThought)
                .where(AgentThought.merchant_id == self.merchant_id)
                .order_by(desc(AgentThought.created_at))
                .limit(limit)
            )
            
            if agent_type:
                query = query.where(AgentThought.agent_type == agent_type)
            
            if product_id:
                # Filter by product_id in detailed_reasoning JSON
                # This requires the product_id to be stored in reasoning
                # FIXME: astext not available in this SQLAlchemy version
                # query = query.where(
                #     AgentThought.detailed_reasoning['product_id'].astext == product_id
                # )
                pass  # Skip product_id filtering for now

            
            result = await session.execute(query)
            thoughts = result.scalars().all()
            
            return [
                {
                    'agent': t.agent_type,
                    'type': t.thought_type,
                    'summary': t.summary,
                    'reasoning': t.detailed_reasoning,
                    'created_at': t.created_at.isoformat() if t.created_at else None,
                }
                for t in thoughts
            ]
