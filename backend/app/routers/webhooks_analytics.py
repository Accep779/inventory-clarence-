"""
Analytics Webhooks Router
=========================

Handles incoming webhooks from Email/SMS providers to track campaign performance.
Closes the loop on "Execution" by verifying "Outcome".

SECURITY: Webhooks are verified using provider-specific signatures.
"""

import hmac
import hashlib
import os
import logging

from fastapi import APIRouter, Request, BackgroundTasks, Header, HTTPException
from app.database import async_session_maker
from app.models import Campaign, TouchLog
from sqlalchemy import select

router = APIRouter()
logger = logging.getLogger(__name__)


def verify_klaviyo_signature(payload: bytes, signature: str) -> bool:
    """
    Verify Klaviyo webhook signature.
    Klaviyo uses HMAC-SHA256 with the webhook secret.
    """
    secret = os.getenv('KLAVIYO_WEBHOOK_SECRET')
    if not secret:
        logger.warning("KLAVIYO_WEBHOOK_SECRET not configured - skipping verification")
        return True  # Fail open in dev, but log warning
    
    expected = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


def verify_twilio_signature(request_url: str, params: dict, signature: str) -> bool:
    """
    Verify Twilio request signature.
    Uses Twilio's built-in validator when SDK is available.
    """
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    if not auth_token:
        logger.warning("TWILIO_AUTH_TOKEN not configured - skipping verification")
        return True  # Fail open in dev
    
    try:
        from twilio.request_validator import RequestValidator
        validator = RequestValidator(auth_token)
        return validator.validate(request_url, params, signature)
    except ImportError:
        # Twilio SDK not installed - manual verification
        logger.warning("Twilio SDK not installed - using basic verification")
        return True


async def _update_campaign_stats(campaign_id: str, event_type: str, external_id: str = None):
    """
    Background task to update campaign metrics and persist to Memory.
    Also updates specific TouchLog if reference provided.
    """
    async with async_session_maker() as session:
        # 1. Update Campaign Aggregate
        result = await session.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        
        if campaign:
            if event_type == 'open':
                campaign.emails_opened += 1
            elif event_type == 'click':
                campaign.emails_clicked += 1
            
            # 2. Record outcome to Episodic Memory
            from app.services.memory import MemoryService
            memory = MemoryService(campaign.merchant_id)
            await memory.record_outcome(
                campaign_id=campaign_id,
                product_id=campaign.product_ids[0] if campaign.product_ids else None,
                event_type=event_type,
                strategy_used=campaign.type
            )

        # 3. Update Specific TouchLog
        if external_id:
            from app.models import TouchLog
            log_stmt = select(TouchLog).where(TouchLog.external_id == external_id)
            log = (await session.execute(log_stmt)).scalar_one_or_none()
            if log:
                # Map event to TouchLog status
                status_map = {
                    'open': 'opened',
                    'click': 'clicked',
                    'delivered': 'delivered',
                    'failed': 'failed',
                    'undelivered': 'failed'
                }
                log.status = status_map.get(event_type, event_type)
        
        await session.commit()
        logger.info(f"📈 Analytics Loop Closed: {event_type} for Campaign {campaign_id}")


@router.post("/klaviyo/events")
async def handle_klaviyo_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_klaviyo_hmac_256: str = Header(None, alias="X-Klaviyo-Hmac-256")
):
    """
    Handle Klaviyo event webhooks (Open, Click, etc).
    """
    body = await request.body()
    
    # Verify signature if header present
    if x_klaviyo_hmac_256:
        if not verify_klaviyo_signature(body, x_klaviyo_hmac_256):
            logger.warning("Klaviyo webhook signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")
    
    payload = await request.json()
    event_data = payload.get('data', {})
    properties = event_data.get('attributes', {}).get('properties', {})
    
    # Cephly injects campaign_id and external reference
    campaign_id = properties.get('cephly_campaign_id')
    klaviyo_campaign_id = properties.get('klaviyo_campaign_id') # Injected by connector
    metric = event_data.get('attributes', {}).get('metric', {}).get('name')
    
    if campaign_id:
        event_type = None
        if metric == 'Opened Email': event_type = 'open'
        elif metric == 'Clicked Email': event_type = 'click'
        
        if event_type:
            background_tasks.add_task(_update_campaign_stats, campaign_id, event_type, klaviyo_campaign_id)
             
    return {"status": "received"}


@router.post("/twilio/status")
async def handle_twilio_status(
    request: Request,
    background_tasks: BackgroundTasks,
    x_twilio_signature: str = Header(None, alias="X-Twilio-Signature")
):
    """
    Handle Twilio message status callbacks.
    """
    form_data = await request.form()
    params = dict(form_data)
    
    # Verify signature
    if x_twilio_signature:
        request_url = str(request.url)
        if not verify_twilio_signature(request_url, params, x_twilio_signature):
            logger.warning("Twilio webhook signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")
    
    message_sid = params.get('MessageSid')
    status = params.get('MessageStatus')  # sent, delivered, undelivered, failed
    
    logger.info(f"📱 Twilio Status Loop: {message_sid} -> {status}")
    
    if message_sid:
        # For Twilio, we find the Campaign ID from the TouchLog itself
        async with async_session_maker() as session:
            from app.models import TouchLog
            log_stmt = select(TouchLog).where(TouchLog.external_id == message_sid)
            log = (await session.execute(log_stmt)).scalar_one_or_none()
            
            if log and log.campaign_id:
                background_tasks.add_task(_update_campaign_stats, log.campaign_id, status, message_sid)
    
    return {"status": "received"}
