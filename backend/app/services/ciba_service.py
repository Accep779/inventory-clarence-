"""
CIBA Authorization Service
==========================

Client Initiated Back-channel Authentication service.
Enables agents to request real-time authorization from merchants.

Implements Auth0's Async OAuth pattern:
- Push notifications for high-risk operations
- Redis pub/sub for real-time decision notification
- Rich Authorization Request (RAR) details
- Timeout fallback to manual dashboard approval
"""

import uuid
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple

from sqlalchemy import select

from app.database import async_session_maker
from app.models import AsyncAuthorizationRequest, Merchant, InboxItem
from app.redis import get_redis_client

from app.services.notifications.sms import TwilioService

logger = logging.getLogger(__name__)


class CIBAService:
    """
    Client Initiated Back-channel Authentication service.
    Enables agents to request real-time authorization from merchants.
    """
    
    DEFAULT_TIMEOUT = 300  # 5 minutes
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self.redis = get_redis_client()
        self.sms_service = TwilioService()
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    async def initiate_authorization(
        self,
        agent_type: str,
        operation_type: str,
        authorization_details: Dict[str, Any],
        inbox_item_id: Optional[str] = None,
        timeout_seconds: int = DEFAULT_TIMEOUT,
        notification_channels: List[str] = None
    ) -> AsyncAuthorizationRequest:
        """
        Initiate a CIBA-style authorization request.
        """
        if notification_channels is None:
            notification_channels = ["push", "email"]
            
        # Get merchant for channel validation
        merchant = await self._get_merchant()
        if not merchant:
             logger.error(f"Merchant {self.merchant_id} not found for CIBA")
             # Proceed anyway, will fail at notification step
        
        # [Day 0 Reliability] Channel Fallback Strategy
        # 1. Prefer Push (Mobile App)
        # 2. Fallback to SMS (Magic Link)
        # 3. Fallback to Dashboard (Manual)
        if merchant:
            has_app = getattr(merchant, "fcm_token", None)
            has_phone = getattr(merchant, "phone", None)
            
            if "push" in notification_channels and not has_app:
                notification_channels.remove("push")
                logger.info("No mobile app detected. Falling back from Push.")
                
                if has_phone:
                    if "sms" not in notification_channels:
                        notification_channels.append("sms")
                        logger.info("Falling back to SMS.")
                else:
                    if "dashboard" not in notification_channels:
                        notification_channels.append("dashboard")
                        logger.info("Falling back to Dashboard.")

        auth_req_id = f"cephly_ciba_{uuid.uuid4().hex[:16]}"
        
        request = AsyncAuthorizationRequest(
            merchant_id=self.merchant_id,
            auth_req_id=auth_req_id,
            inbox_item_id=inbox_item_id,
            agent_type=agent_type,
            operation_type=operation_type,
            authorization_details=authorization_details,
            expires_at=datetime.utcnow() + timedelta(seconds=timeout_seconds)
        )
        
        # Save to database
        async with async_session_maker() as session:
            session.add(request)
            await session.commit()
            await session.refresh(request)
        
        # Dispatch notifications
        await self._send_notifications(request, notification_channels)
        
        logger.info(f"Initiated CIBA request {auth_req_id} for {operation_type}")
        return request
    
    async def wait_for_authorization(
        self, 
        auth_req_id: str, 
        max_wait: int = DEFAULT_TIMEOUT
    ) -> Tuple[str, Optional[Dict]]:
        """
        Wait for authorization using Redis pub/sub (non-blocking).
        
        This uses Redis pub/sub instead of polling to avoid blocking Celery workers.
        
        Args:
            auth_req_id: The CIBA request ID to wait for
            max_wait: Maximum seconds to wait
            
        Returns:
            Tuple of (status, authorization_details or None)
        """
        channel = f"ciba:{auth_req_id}"
        pubsub = self.redis.pubsub()
        pubsub.subscribe(channel)
        
        try:
            start_time = datetime.utcnow()
            
            while (datetime.utcnow() - start_time).seconds < max_wait:
                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
                
                if message and message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        logger.info(f"CIBA response received: {data['status']}")
                        return data['status'], data.get('details')
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Invalid CIBA message format: {e}")
                
                # Brief async yield to prevent blocking
                await asyncio.sleep(0.1)
            
            # Timeout - handle gracefully
            await self._handle_timeout(auth_req_id)
            return "timeout", None
            
        finally:
            pubsub.unsubscribe(channel)
    
    async def process_decision(
        self, 
        auth_req_id: str, 
        decision: str,
        decision_channel: str = "dashboard"
    ) -> Dict[str, Any]:
        """
        Process merchant decision and notify waiting agent via Redis pub/sub.
        
        Args:
            auth_req_id: The CIBA request ID
            decision: "approved" or "rejected"
            decision_channel: How the decision was made (mobile_push, sms, dashboard)
            
        Returns:
            Result dict with success status
        """
        async with async_session_maker() as session:
            result = await session.execute(
                select(AsyncAuthorizationRequest).where(
                    AsyncAuthorizationRequest.auth_req_id == auth_req_id
                )
            )
            request = result.scalar_one_or_none()
            
            if not request:
                return {"success": False, "error": "Request not found"}
            
            if request.status not in ("pending", "pending_manual"):
                return {"success": False, "error": f"Request already {request.status}"}
            
            # Update request
            request.status = decision
            request.decided_at = datetime.utcnow()
            request.decision_channel = decision_channel
            await session.commit()
        
        # Publish decision to Redis for waiting agent
        self.redis.publish(
            f"ciba:{auth_req_id}",
            json.dumps({
                "status": decision,
                "details": request.authorization_details
            })
        )
        
        # Also update linked InboxItem if present
        if request.inbox_item_id:
            await self._update_inbox_item(
                request.inbox_item_id, 
                "approved" if decision == "approved" else "rejected"
            )
        
        logger.info(f"CIBA request {auth_req_id} {decision} via {decision_channel}")
        return {"success": True, "status": decision}
    
    async def get_pending_requests(self) -> List[AsyncAuthorizationRequest]:
        """Get all pending CIBA requests for this merchant."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(AsyncAuthorizationRequest).where(
                    AsyncAuthorizationRequest.merchant_id == self.merchant_id,
                    AsyncAuthorizationRequest.status.in_(["pending", "pending_manual"])
                ).order_by(AsyncAuthorizationRequest.created_at.desc())
            )
            return result.scalars().all()
    
    # =========================================================================
    # TIMEOUT HANDLING
    # =========================================================================
    
    async def _handle_timeout(self, auth_req_id: str):
        """
        Handle timeout gracefully - keep request open for manual approval.
        
        1. InboxItem stays open for later approval
        2. Schedule reminder notification for 24h later
        3. Allow retroactive approval via dashboard
        """
        async with async_session_maker() as session:
            result = await session.execute(
                select(AsyncAuthorizationRequest).where(
                    AsyncAuthorizationRequest.auth_req_id == auth_req_id
                )
            )
            request = result.scalar_one_or_none()
            
            if request and request.status == "pending":
                # Mark as expired for Red Team strictness / Day 0 security
                request.status = "expired"
                await session.commit()
                
                # Also update linked InboxItem if present
                if request.inbox_item_id:
                    await self._update_inbox_item(request.inbox_item_id, "failed")
                
                # Schedule reminder (via Celery)
                self._schedule_reminder(auth_req_id)
                
                logger.info(f"CIBA request {auth_req_id} timed out, marked for manual approval")
    
    def _schedule_reminder(self, auth_req_id: str):
        """Schedule a reminder notification for 24 hours later."""
        try:
            from app.tasks.notifications import schedule_ciba_reminder
            schedule_ciba_reminder.apply_async(
                args=[self.merchant_id, auth_req_id],
                countdown=86400  # 24 hours
            )
        except Exception as e:
            logger.warning(f"Could not schedule reminder: {e}")
    
    # =========================================================================
    # NOTIFICATIONS
    # =========================================================================
    
    async def _send_notifications(
        self, 
        request: AsyncAuthorizationRequest, 
        channels: List[str]
    ):
        """Send push notification, SMS, and/or email to merchant."""
        merchant = await self._get_merchant()
        if not merchant:
            logger.error(f"Cannot send notifications - merchant {self.merchant_id} not found")
            return
        
        # Format rich authorization details for display
        message = self._format_authorization_message(request)
        
        for channel in channels:
            try:
                if channel == "push":
                    await self._send_push_notification(merchant, message, request)
                elif channel == "sms" and merchant.phone:
                    await self._send_sms(merchant.phone, message, request)
                elif channel == "email":
                    await self._send_email(merchant.email, message, request)
            except Exception as e:
                logger.warning(f"Failed to send {channel} notification: {e}")
    
    def _format_authorization_message(self, request: AsyncAuthorizationRequest) -> str:
        """Format RAR details into a human-readable message."""
        details = request.authorization_details
        
        msg_parts = [f"Agent needs your approval:"]
        
        if "type" in details:
            msg_parts.append(f"Action: {details['type'].replace('_', ' ').title()}")
        
        if "campaign_name" in details:
            msg_parts.append(f"Campaign: {details['campaign_name']}")
        
        if "discount_percentage" in details:
            msg_parts.append(f"Discount: {int(details['discount_percentage'] * 100)}%")
        
        if "target_customers" in details:
            msg_parts.append(f"Target: {details['target_customers']} customers")
        
        if "estimated_revenue" in details:
            msg_parts.append(f"Est. Revenue: ${details['estimated_revenue']:,.2f}")
        
        if "products" in details and details["products"]:
            products = details["products"][:3]  # First 3 products
            msg_parts.append(f"Products: {', '.join(products)}")
            if len(details["products"]) > 3:
                msg_parts.append(f"  (+{len(details['products']) - 3} more)")
        
        return "\n".join(msg_parts)
    
    async def _send_push_notification(
        self, 
        merchant: Merchant, 
        message: str, 
        request: AsyncAuthorizationRequest
    ):
        """Send Firebase push notification."""
        # Log for now - integrate with Firebase later
        logger.info(
            f"PUSH NOTIFICATION:\n"
            f"  To: Merchant {merchant.store_name}\n"
            f"  Message: {message}\n"
            f"  Request ID: {request.auth_req_id}"
        )
        
        # Update sent timestamp
        async with async_session_maker() as session:
            result = await session.execute(
                select(AsyncAuthorizationRequest).where(
                    AsyncAuthorizationRequest.id == request.id
                )
            )
            req = result.scalar_one_or_none()
            if req:
                req.push_sent_at = datetime.utcnow()
                await session.commit()
    
    async def _send_sms(
        self, 
        phone: str, 
        message: str, 
        request: AsyncAuthorizationRequest
    ):
        """Send Twilio SMS with Magic Link."""
        
        # [Day 0 Reliability] Send Magic Link instead of just text
        magic_link = f"https://app.cephly.com/approve/{request.auth_req_id}"
        
        sms_body = (
            f"Cephly: {request.agent_type.capitalize()} Agent needs approval for "
            f"{request.operation_type}. Tap to review: {magic_link}"
        )
        
        success = await self.sms_service.send_sms(phone, sms_body)
        
        if success:
            # Update sent timestamp
            async with async_session_maker() as session:
                result = await session.execute(
                    select(AsyncAuthorizationRequest).where(
                        AsyncAuthorizationRequest.id == request.id
                    )
                )
                req = result.scalar_one_or_none()
                if req:
                    req.sms_sent_at = datetime.utcnow()
                    await session.commit()
    
    async def _send_email(
        self, 
        email: str, 
        message: str, 
        request: AsyncAuthorizationRequest
    ):
        """Send email notification."""
        logger.info(
            f"EMAIL:\n"
            f"  To: {email}\n"
            f"  Subject: Approval Needed: {request.operation_type.replace('_', ' ').title()}\n"
            f"  Body: {message}"
        )
        
        # Update sent timestamp
        async with async_session_maker() as session:
            result = await session.execute(
                select(AsyncAuthorizationRequest).where(
                    AsyncAuthorizationRequest.id == request.id
                )
            )
            req = result.scalar_one_or_none()
            if req:
                req.email_sent_at = datetime.utcnow()
                await session.commit()
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    async def _get_merchant(self) -> Optional[Merchant]:
        """Fetch merchant for notification."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Merchant).where(Merchant.id == self.merchant_id)
            )
            return result.scalar_one_or_none()
    
    async def _update_inbox_item(self, inbox_item_id: str, status: str):
        """Update linked InboxItem status."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(InboxItem).where(
                    InboxItem.id == inbox_item_id,
                    InboxItem.merchant_id == self.merchant_id  # Tenant isolation
                )
            )
            item = result.scalar_one_or_none()
            if item:
                item.status = status
                item.decided_at = datetime.utcnow()
                await session.commit()
                logger.debug(f"Updated InboxItem {inbox_item_id} to {status}")
