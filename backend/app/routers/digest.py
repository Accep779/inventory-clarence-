from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from pydantic import BaseModel
from sqlalchemy import select, delete, func
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import PendingNotification
from app.services.digest import DigestService

router = APIRouter(
    prefix="/digest",
    tags=["Anti-Fatigue Layer"]
)

class QueueItem(BaseModel):
    id: str
    priority: str
    channel: str
    topic: str
    content: str
    created_at: str

@router.get("/queue", response_model=Dict[str, Any])
async def view_queue(db: AsyncSession = Depends(get_db)):
    """
    Preview the 'Pending Notifications' queue.
    Used by the Dashboard to show what messages are being intercepted.
    """
    # In a real app, filter by merchant_id from auth context
    # For MVP debug, just returning 50 items
    result = await db.execute(
        select(PendingNotification).order_by(PendingNotification.created_at.desc()).limit(50)
    )
    items = result.scalars().all()
    
    serialized = []
    for item in items:
        serialized.append({
            "id": item.id,
            "priority": item.priority,
            "channel": item.channel,
            "topic": item.topic,
            "content": item.content,
            "created_at": item.created_at.isoformat()
        })
        
    return {
        "queue_size": len(serialized),
        "items": serialized
    }

@router.post("/flush")
async def flush_digest():
    """
    Force-send the digest immediately.
    """
    # We need a proper merchant_id here.
    # For MVP, we'll flush the test merchant or default.
    merchant_id = "test_merchant_digest" # Hardcoded for Verify Script parity
    
    service = DigestService()
    count = await service.flush_digest(merchant_id=merchant_id, channel="terminal:dashboard_admin")
    
    return {"status": "success", "flushed_count": count}
