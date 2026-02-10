
import logging
from uuid import uuid4
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any, Dict, List
from sqlalchemy import select, desc
from app.database import async_session_maker
from app.models import AgentThought

logger = logging.getLogger(__name__)

class ThoughtLogger:
    """
    Captures agent reasoning and step-by-step logic.
    Surfaces the 'Internal Monologue' of Cephly to merchants.
    """
    
    @staticmethod
    async def log_thought(
        merchant_id: str,
        agent_type: str,
        thought_type: str,
        summary: str,
        detailed_reasoning: Optional[Dict[str, Any]] = None,
        execution_id: Optional[str] = None,
        evidence: Optional[Dict[str, Any]] = None,  # Forensic snapshots (e.g., Order IDs)
        confidence_score: float = 1.0,
        step_number: int = 1,
        product_id: Optional[str] = None,
        **kwargs
    ) -> AgentThought:
        """
        Records a single reasoning step in the database.
        
        Args:
            merchant_id: ID of the merchant the thought relates to.
            agent_type: observer, strategy, matchmaker, etc.
            thought_type: analysis, decision, calculation, warning.
            summary: Concise narrative for the merchant.
            detailed_reasoning: Full structured data behind the thought.
            execution_id: Optional UUID to group related thoughts.
            evidence: Explicit data snapshots that influenced this thought.
            confidence_score: 0-1 score indicating agent certainty.
            step_number: Sequence number of the thought within a larger process.
        """
        # Merge evidence/product_id into detailed_reasoning if provided
        detailed_reasoning = detailed_reasoning or {}
        if evidence:
            detailed_reasoning["_forensic_evidence"] = evidence
        if product_id:
            detailed_reasoning["product_id"] = product_id
        if kwargs:
            detailed_reasoning["_extra_metadata"] = kwargs

        async with async_session_maker() as session:
            thought = AgentThought(
                merchant_id=merchant_id,
                agent_type=agent_type,
                thought_type=thought_type,
                summary=summary,
                detailed_reasoning=detailed_reasoning,
                execution_id=execution_id,
                confidence_score=Decimal(str(confidence_score)),
                step_number=step_number,
                created_at=datetime.utcnow()
            )
            session.add(thought)
            await session.commit()
            await session.refresh(thought)
            
            logger.info(f"AgentThought [{agent_type}] logged for merchant {merchant_id}: {summary}")
            
            # TODO: Emit WebSocket event for real-time frontend updates
            
            return thought

    @staticmethod
    async def recall_thoughts(
        merchant_id: str,
        agent_type: Optional[str] = None,
        execution_id: Optional[str] = None,
        limit: int = 10
    ) -> List[AgentThought]:
        """
        Retrieves past thoughts for context injection.
        
        This is the READ side of memory, enabling agents to recall
        their previous reasoning about specific situations.
        
        Args:
            merchant_id: ID of the merchant.
            agent_type: Optional filter by agent (observer, strategy, etc.)
            execution_id: Optional filter by specific execution run.
            limit: Maximum number of thoughts to retrieve.
        
        Returns:
            List of AgentThought objects, ordered by most recent first.
        """
        async with async_session_maker() as session:
            query = (
                select(AgentThought)
                .where(AgentThought.merchant_id == merchant_id)
                .order_by(desc(AgentThought.created_at))
                .limit(limit)
            )
            
            if agent_type:
                query = query.where(AgentThought.agent_type == agent_type)
            
            if execution_id:
                query = query.where(AgentThought.execution_id == execution_id)
            
            result = await session.execute(query)
            thoughts = result.scalars().all()
            
            logger.info(f"ThoughtLogger: Recalled {len(thoughts)} thoughts for merchant {merchant_id}")
            return thoughts
