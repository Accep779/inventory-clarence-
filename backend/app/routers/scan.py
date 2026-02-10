"""
Scan Router - Real-Time Dead Stock Scanning for Onboarding.

Provides:
- POST /api/scan/start - Start quick scan, returns session_id
- GET /api/scan/stream/{session_id} - SSE stream for live updates
- GET /api/scan/status/{session_id} - Poll fallback for scan status
"""

import asyncio
import json
from uuid import uuid4
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from app.database import async_session_maker
from app.models import Merchant
from app.services.scan_broadcaster import get_broadcaster
from app.tasks.quick_scan import start_quick_scan
from app.auth_middleware import get_current_tenant
from sqlalchemy import select

router = APIRouter()


class ScanStartResponse(BaseModel):
    session_id: str
    message: str


@router.post("/start", response_model=ScanStartResponse)
async def start_scan(merchant_id: str = Depends(get_current_tenant)):
    """
    Start a quick scan for onboarding.
    
    Requires authentication. Triggers Celery task and returns session_id for SSE subscription.
    """
    # Verify merchant exists
    async with async_session_maker() as session:
        result = await session.execute(
            select(Merchant).where(Merchant.id == merchant_id)
        )
        merchant = result.scalar_one_or_none()
        
        if not merchant:
            raise HTTPException(status_code=404, detail="Merchant not found")
        
        if not merchant.access_token:
            raise HTTPException(status_code=400, detail="Shopify not connected")
            
        # [Day 0 Reliability] Block scan if sync is in progress
        if merchant.sync_status in ("pending", "syncing"):
            return JSONResponse(
                status_code=409,
                content={
                    "error": "sync_in_progress",
                    "message": "Initial data sync in progress. Please wait.",
                    "retry_after": 5
                }
            )
    
    # Generate unique session ID
    session_id = str(uuid4())
    
    # Start Temporal Workflow
    from temporalio.client import Client
    
    # We connect on every request for simplicity in this phase, 
    # but efficient app would have a global client dependency.
    client = await Client.connect("temporal:7233", namespace="default")
    
    await client.execute_workflow(
        "QuickScanWorkflow",
        {"merchant_id": merchant_id, "session_id": session_id},
        id=f"quick-scan-{session_id}",
        task_queue="execution-agent-queue"
    )
    
    # Legacy: start_quick_scan.delay(merchant_id, session_id)
    
    return ScanStartResponse(
        session_id=session_id,
        message="Scan started. Subscribe to /api/scan/stream/{session_id} for live updates."
    )


@router.get("/stream/{session_id}")
async def stream_scan_events(session_id: str):
    """
    Server-Sent Events endpoint for live scan updates.
    
    Events:
    - scan_progress: {products_scanned, total_products}
    - dead_stock_found: {product, running_total}
    - quick_scan_complete: {summary}
    - error: {error}
    """
    
    async def event_generator():
        broadcaster = get_broadcaster()
        pubsub = broadcaster.get_pubsub(session_id)
        
        # Send initial connected event
        yield f"event: connected\ndata: {json.dumps({'session_id': session_id})}\n\n"
        
        try:
            while True:
                # Non-blocking message check
                message = pubsub.get_message(timeout=0.5)
                
                if message and message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    
                    # Parse to get event type
                    try:
                        parsed = json.loads(data)
                        event_type = parsed.get("type", "message")
                        
                        yield f"event: {event_type}\ndata: {data}\n\n"
                        
                        # End stream on completion or error
                        if event_type in ("quick_scan_complete", "error"):
                            break
                    except json.JSONDecodeError:
                        yield f"event: message\ndata: {data}\n\n"
                
                # Small delay to prevent CPU spinning
                await asyncio.sleep(0.1)
        
        finally:
            pubsub.unsubscribe()
            pubsub.close()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/status/{session_id}")
async def get_scan_status(session_id: str):
    """
    Polling fallback for scan status.
    
    Returns latest status from Redis if SSE not available.
    """
    broadcaster = get_broadcaster()
    redis = broadcaster.redis
    
    # Check for completion status
    status_key = f"scan_status:{session_id}"
    status = redis.get(status_key)
    
    if status:
        return json.loads(status)
    
    return {
        "status": "in_progress",
        "message": "Scan is running. Use SSE endpoint for real-time updates."
    }


# Quick start endpoint - combines OAuth check + scan start
@router.post("/quick-start")
async def quick_start_scan(merchant_id: str = Depends(get_current_tenant)):
    """
    Quick start scan for merchant.
    
    Used immediately after OAuth callback.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(Merchant).where(Merchant.id == merchant_id)
        )
        merchant = result.scalar_one_or_none()
        
        if not merchant:
            raise HTTPException(status_code=404, detail="Merchant not found")
            
        # [Day 0 Reliability] Block scan if sync is in progress
        if merchant.sync_status in ("pending", "syncing"):
            return JSONResponse(
                status_code=409,
                content={
                    "error": "sync_in_progress",
                    "message": "Initial data sync in progress. Please wait.",
                    "retry_after": 5
                }
            )
    
    session_id = str(uuid4())
    start_quick_scan.delay(merchant_id, session_id)
    
    return {
        "session_id": session_id,
        "stream_url": f"/api/scan/stream/{session_id}",
        "status": "started"
    }
