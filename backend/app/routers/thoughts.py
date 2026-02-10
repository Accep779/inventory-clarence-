
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from typing import List, Optional
from app.database import async_session_maker
from app.models import AgentThought
from app.config import Settings, get_settings
from app.auth_middleware import get_current_tenant

router = APIRouter(tags=["Thoughts"])

@router.get("", response_model=List[dict])
async def get_thoughts(
    merchant_id: str = Depends(get_current_tenant),
    execution_id: Optional[str] = None,
    limit: int = 50,
    settings: Settings = Depends(get_settings)
):
    """
    Retrieve agent thoughts for the current merchant.
    Optionally filter by execution_id for a specific process.
    """
    async with async_session_maker() as session:
        query = select(AgentThought).where(AgentThought.merchant_id == merchant_id)
        
        if execution_id:
            query = query.where(AgentThought.execution_id == execution_id)
            
        query = query.order_by(desc(AgentThought.created_at)).limit(limit)
        
        result = await session.execute(query)
        thoughts = result.scalars().all()
        
        return [
            {
                "id": t.id,
                "agent_type": t.agent_type,
                "thought_type": t.thought_type,
                "summary": t.summary,
                "detailed_reasoning": t.detailed_reasoning,
                "execution_id": t.execution_id,
                "confidence_score": float(t.confidence_score),
                "step_number": t.step_number,
                "created_at": t.created_at.isoformat()
            }
            for t in thoughts
        ]

# TODO: Add WebSocket endpoint for real-time streaming
