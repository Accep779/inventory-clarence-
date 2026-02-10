# app/services/memory_stream.py
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import select, and_
from app.database import async_session_maker
from app.models import AgentThought

logger = logging.getLogger(__name__)

class MemoryStreamService:
    """
    Tracks 'Causal History' of agent decisions.
    Provides the 'Brain' layer to prevent repetitive logic failures.
    """
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id

    async def record_decision(self, agent_type: str, cluster_id: str, action: str, reasoning: str, feedback: Optional[str] = None):
        """Records a specific decision related to an inventory cluster or product."""
        async with async_session_maker() as session:
            thought = AgentThought(
                merchant_id=self.merchant_id,
                agent_type=agent_type,
                thought_type="causal_memory",
                summary=f"{action} on {cluster_id}",
                detailed_reasoning={
                    "reasoning": reasoning,
                    "feedback": feedback,
                    "action": action,
                    "cluster_id": cluster_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            session.add(thought)
            await session.commit()
            logger.info(f"🧠 Causal memory recorded for {agent_type} - {action}")

    async def get_relevant_history(self, cluster_themes: List[str], limit: int = 10) -> str:
        """
        Retrieves past decisions that share themes with current clusters.
        Prevents recommending things the merchant already rejected or that failed.
        """
        async with async_session_maker() as session:
            # Query last 30 days of causal memory
            stmt = select(AgentThought).where(
                and_(
                    AgentThought.merchant_id == self.merchant_id,
                    AgentThought.thought_type == "causal_memory",
                    AgentThought.created_at >= datetime.utcnow() - timedelta(days=30)
                )
            ).order_by(AgentThought.created_at.desc()).limit(limit)
            
            result = await session.execute(stmt)
            thoughts = result.scalars().all()
            
            if not thoughts:
                return "No relevant causal history found."

            history_lines = ["## Relevant Causal History (Last 30 Days)"]
            for t in thoughts:
                data = t.detailed_reasoning or {}
                # Basic fuzzy matching on themes if provided
                is_relevant = any(theme.lower() in t.summary.lower() for theme in cluster_themes) if cluster_themes else True
                
                if is_relevant:
                    history_lines.append(
                        f"- [{t.created_at.strftime('%Y-%m-%d')}] {t.summary}: {data.get('reasoning', '')} "
                        f"(Feedback: {data.get('feedback', 'None')})"
                    )
            
            return "\n".join(history_lines)
