"""
Inbox API Router.

The Inbox is the "Control Surface" for the agent system.
Merchants see proposals from agents and approve/reject/edit them.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends, Request, Header
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import json
from redis.asyncio import from_url

from app.database import get_db
from app.models import InboxItem, Merchant
from app.auth_middleware import get_current_tenant
from app.config import get_settings
from app.services.inbox import InboxService
from app.middleware.idempotency import get_idempotency_middleware, IdempotencyError

router = APIRouter()
settings = get_settings()

@router.get("/stream")
async def stream_inbox_updates(
    request: Request,
    merchant_id: str = Depends(get_current_tenant)
):
    """
    Server-Sent Events endpoint for real-time inbox updates.
    Frontend connects to this to get instant "pings" when agents act.
    """
    async def event_generator():
        redis = await from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = redis.pubsub()
        channel = f"inbox_updates:{merchant_id}"
        await pubsub.subscribe(channel)
        
        logger = InboxService.logger if hasattr(InboxService, 'logger') else None
        
        try:
            # Send initial "connected" event
            yield {
                "event": "connected",
                "data": json.dumps({"status": "live", "merchant_id": merchant_id})
            }
            
            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    break
                
                # Wait for message with timeout to allow checking disconnect
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    yield {
                        "event": "update",
                        "data": message["data"]
                    }
                
                # Small sleep to prevent tight loop if no messages
                await asyncio.sleep(0.1)
        
        finally:
            await pubsub.unsubscribe(channel)
            await redis.close()

    return EventSourceResponse(event_generator())

class InboxItemResponse(BaseModel):
    """Response model for inbox items."""
    id: str
    type: str
    status: str
    agent_type: str
    confidence: Optional[float]
    proposal_data: dict
    chat_history: Optional[List[dict]] = []
    viewed_at: Optional[datetime]
    decided_at: Optional[datetime]
    executed_at: Optional[datetime]
    created_at: datetime
    
    # CIBA / Async Auth
    waiting_for_mobile_auth: bool = False
    mobile_auth_status: Optional[str] = None

    class Config:
        from_attributes = True


class InboxListResponse(BaseModel):
    """Response model for inbox list."""
    items: List[InboxItemResponse]
    pending_count: int


@router.get("", response_model=InboxListResponse)
async def list_inbox_items(
    merchant_id: str = Depends(get_current_tenant),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """List all inbox items for a merchant."""
    service = InboxService(db, merchant_id)
    items, pending_count = await service.list_proposals(status=status, limit=limit, offset=offset)
    
    return InboxListResponse(
        items=[InboxItemResponse.model_validate(item) for item in items],
        pending_count=pending_count
    )


@router.get("/{item_id}", response_model=InboxItemResponse)
async def get_inbox_item(
    item_id: str,
    merchant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific inbox item."""
    service = InboxService(db, merchant_id)
    item = await service.get_proposal(item_id)
    
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    
    return InboxItemResponse.model_validate(item)


@router.post("/{item_id}/approve")
async def approve_inbox_item(
    item_id: str,
    merchant_id: str = Depends(get_current_tenant),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve an agent's proposal.
    
    Supports optional Idempotency-Key header to prevent duplicate approvals.
    If provided, duplicate requests with the same key will return cached result.
    """
    async def _approve_internal():
        service = InboxService(db, merchant_id)
        item, error = await service.approve_proposal(item_id)
        
        if error:
            if "not found" in error.lower():
                raise HTTPException(status_code=404, detail="Inbox item not found")
            raise HTTPException(status_code=400, detail=error)
        
        return {"status": "approved", "item_id": item_id}
    
    # If idempotency key provided, use middleware
    if idempotency_key:
        try:
            idempotency = get_idempotency_middleware()
            return await idempotency.ensure_idempotent(
                key=idempotency_key,
                merchant_id=merchant_id,
                endpoint=f"/inbox/{item_id}/approve",
                handler=_approve_internal
            )
        except IdempotencyError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # No idempotency key - execute directly (backward compatible)
    return await _approve_internal()


@router.post("/{item_id}/reject")
async def reject_inbox_item(
    item_id: str,
    merchant_id: str = Depends(get_current_tenant),
    reason: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Reject an agent's proposal."""
    service = InboxService(db, merchant_id)
    item, error = await service.reject_proposal(item_id, reason)
    
    if error:
        if "not found" in error.lower():
            raise HTTPException(status_code=404, detail="Inbox item not found")
        raise HTTPException(status_code=400, detail=error)
    
    return {"status": "rejected", "item_id": item_id}





@router.patch("/{item_id}/items")
async def remove_item_from_proposal(
    item_id: str,
    sku: str = Query(...),
    merchant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Remove a specific SKU from a batch proposal before approval."""
    service = InboxService(db, merchant_id)
    item, error = await service.remove_item_from_batch(item_id, sku)
    
    if error:
        raise HTTPException(status_code=400, detail=error)
        
    return InboxItemResponse.model_validate(item)

    return InboxItemResponse.model_validate(item)


class ChatRequest(BaseModel):
    message: str

@router.post("/{item_id}/chat", response_model=InboxItemResponse)
async def chat_with_agent(
    item_id: str,
    payload: ChatRequest,
    merchant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a message to the agent about this proposal.
    The agent may reply and/or update the proposal data.
    """
    service = InboxService(db, merchant_id)
    item, error = await service.chat_with_agent(item_id, payload.message)
    
    if error:
        raise HTTPException(status_code=400, detail=error)
        
    return InboxItemResponse.model_validate(item)
