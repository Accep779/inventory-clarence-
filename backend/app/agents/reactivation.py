# app/agents/reactivation.py
"""
Reactivation Agent
==================
Identifies dormant customers and manages re-engagement journeys.
EXTRACTED FROM: Cephly architecture
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func
from app.database import async_session_maker
from app.models import Customer, CommercialJourney, TouchLog, Merchant
from app.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)

from app.services.memory import MemoryService
# from app.services.thought_logger import ThoughtLogger # Removed direct dependency

class ReactivationAgent:
    """
    World-Class Reactivation Agent.
    
    Acts as the customer journey architect, reasoning about *why* customers 
    leave and *how* to bring them back.
    """
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self.router = LLMRouter()
        self.memory = MemoryService(merchant_id)
        self.agent_type = "reactivation"
        self.client_id = f"agent_{self.agent_type}_{merchant_id[:4]}"
        self._api_token = None

    async def _authenticate(self):
        """[HARDENING] Authenticates with Internal API using Vaulted Credentials."""
        if self._api_token: return
        import aiohttp
        from app.services.identity import IdentityService
        from app.database import async_session_maker
        async with async_session_maker() as db:
            identity_service = IdentityService(db, self.merchant_id)
            creds = await identity_service.get_agent_credentials("reactivation")
        if not creds:
             logger.error("Failed to fetch Reactivation credentials")
             return
        async with aiohttp.ClientSession() as http:
            async with http.post("http://localhost:8000/internal/agents/auth", json=creds) as resp:
                if resp.status == 200:
                     self._api_token = (await resp.json())['access_token']
                else:
                     logger.error(f"Reactivation Auth Failed: {await resp.text()}")

    async def _log_thought(self, **kwargs):
        """Helper to log thoughts via Internal API."""
        if not self._api_token: await self._authenticate()
        
        import aiohttp
        headers = {"Authorization": f"Bearer {self._api_token}"}
        
        # Map kwargs to API schema
        payload = {
            "agent_type": self.agent_type,
            "thought_type": kwargs.get("thought_type", "info"),
            "summary": kwargs.get("summary", ""),
            "detailed_reasoning": kwargs.get("detailed_reasoning", {}),
            "confidence_score": float(kwargs.get("confidence_score", 1.0)),
            "step_number": kwargs.get("step_number", 1),
            "execution_id": kwargs.get("execution_id"),
            "product_id": kwargs.get("detailed_reasoning", {}).get("product_id") or kwargs.get("product_id")
        }
        # Add customer_id to detailed reasoning if standalone (legacy compat)
        if kwargs.get("customer_id"):
             payload["detailed_reasoning"]["customer_id"] = kwargs.get("customer_id")
        
        try:
            async with aiohttp.ClientSession() as http:
                await http.post(
                    "http://localhost:8000/internal/agents/thoughts",
                    json=payload,
                    headers=headers
                )
        except Exception as e:
            logger.error(f"Failed to log thought via API: {e}")

    async def scan_for_dormant_customers(self):
        """
        Cognitive Trigger: Uses LLM to identify customers who are *sliding* 
        into dormancy, not just those who passed a fixed day count.
        """
        async with async_session_maker() as session:
            # 1. GATHER: High-value customers who haven't ordered recently
            # We broaden the window to 30-90 days to let the LLM decide
            window_start = datetime.utcnow() - timedelta(days=90)
            window_end = datetime.utcnow() - timedelta(days=30)
            
            stmt = (
                select(Customer)
                .where(Customer.merchant_id == self.merchant_id)
                .where(Customer.last_order_date.between(window_start, window_end))
                .where(Customer.rfm_segment.in_(['champions', 'loyal', 'at_risk']))
            )
            
            result = await session.execute(stmt)
            candidates = result.scalars().all()
            
            cooldown_start = datetime.utcnow() - timedelta(days=90)
            candidate_ids = [c.id for c in candidates]
            
            # 2. BATCH CHECK: Cooldown (customers with any journey in last 90 days)
            cooldown_res = await session.execute(
                select(CommercialJourney.customer_id)
                .where(CommercialJourney.customer_id.in_(candidate_ids))
                .where(CommercialJourney.created_at > cooldown_start)
            )
            cooldown_ids = {row[0] for row in cooldown_res.all()}
            
            for customer in candidates:
                if customer.id in cooldown_ids:
                    continue  # Still in cooldown period
                
                # REASON: Should we start a journey for this specific customer?
                should_reactivate = await self._reason_about_reactivation(customer)
                
                if should_reactivate['approved']:
                    # [SECURE REFACTOR] Use Internal API to start journey
                    await self._authenticate()
                    if self._api_token:
                         import aiohttp
                         headers = {"Authorization": f"Bearer {self._api_token}"}
                         async with aiohttp.ClientSession() as http:
                            await http.post(
                                "http://localhost:8000/internal/agents/reactivation/journey/start",
                                json={
                                    "customer_id": customer.id, 
                                    "reason": should_reactivate['reason'],
                                    "journey_type": 'reactivation'
                                },
                                headers=headers
                            )
                            new_journeys += 1
                    
                    await self._log_thought(
                        thought_type="trigger",
                        summary=f"Started reactivation for {customer.first_name}: {should_reactivate['reason']}",
                        detailed_reasoning=should_reactivate,
                        customer_id=customer.id
                    )
            
            await session.commit()
            logger.info(f"Started {new_journeys} reasoning-based reactivation journeys.")

    async def _reason_about_reactivation(self, customer: Customer) -> Dict:
        """Reason if a customer deserves a reactivation push now."""
        prompt = f"""Reason about reactivating this customer.
        
Customer: {customer.first_name}
RFM Segment: {customer.rfm_segment}
Last Order: {customer.last_order_date}
Total Orders: {customer.total_orders}
Total Spent: ${customer.total_spent}
Avg Order Value: ${customer.avg_order_value}

Is this customer 'slipping' based on their value? Champions might need a push at 40 days, while At-Risk might be expected to wait 60.

Respond with JSON:
{{
    "approved": true/false,
    "reason": "Rationale for starting journey",
    "churn_probability": 0.0-1.0
}}"""
        try:
            res = await self.router.complete(
                task_type='strategy_generation',
                system_prompt="You are a Retention Architect. Spot churn before it happens.",
                user_prompt=prompt,
                merchant_id=self.merchant_id
            )
            content = res['content'].strip()
            if '```' in content: content = content.split('```')[1].replace('json', '')
            return json.loads(content)
        except Exception as e:
            logger.error(f"Reactivation trigger reasoning failed: {e}")
            return {"approved": False, "reason": "Error", "churn_probability": 0}

    async def step_journeys(self):
        """Processes active journeys with adaptive touchpoints."""
        async with async_session_maker() as session:
            stmt = (
                select(CommercialJourney)
                .where(CommercialJourney.merchant_id == self.merchant_id)
                .where(CommercialJourney.status == 'active')
                .where(CommercialJourney.next_touch_due_at <= datetime.utcnow())
            )
            
            result = await session.execute(stmt)
            journeys = result.scalars().all()
            
            for journey in journeys:
                # 0. CONVERSION DETECTION: Check if they ordered since journey started
                customer = await session.get(Customer, journey.customer_id)
                if customer.last_order_date and customer.last_order_date > journey.created_at:
                    journey.status = 'converted'
                    logger.info(f"✨ [Reactivation] Conversion detected for {customer.first_name}! Closing journey.")
                    await self._log_thought(
                        thought_type="conversion",
                        summary=f"Customer converted! Order detected on {customer.last_order_date}.",
                        customer_id=customer.id
                    )
                    continue

                # ADAPTIVE: Reason about the NEXT touch
                past_touches = await session.execute(
                    select(TouchLog).where(TouchLog.journey_id == journey.id)
                )
                
                touch_plan = await self._reason_about_next_touch(customer, journey, past_touches.scalars().all())
                
                await self._execute_touch(journey, customer, touch_plan, session)
                
            await session.commit()

    async def _reason_about_next_touch(self, customer: Customer, journey: CommercialJourney, history: List[TouchLog]) -> Dict:
        """
        [DYNAMIC SKILL INJECTION]
        Replaces the hardcoded state machine with the 7-Touch Framework.
        """
        # [DYNAMIC SKILL INJECTION]
        from app.services.skill_loader import SkillLoader
        loader = SkillLoader()
        skill_framework = ""
        try:
            # Load core reactivation sequence
            react_skill = loader._load_single_skill('customer_reactivation')
            skill_framework += f"\n\nCUSTOMER REACTIVATION FRAMEWORK:\n{react_skill.system_prompt}\n\nApply the 7-Touch Reactivation Sequence logic."
            
            # Load event orchestration playbook
            deployment_skill = loader._load_single_skill('event_clearance_deployment')
            skill_framework += f"\n\nCOORDINATION & DEPLOYMENT FRAMEWORK:\n{deployment_skill.system_prompt}\n\nSynchronize touchpoints with Email, SMS, and Ad timing."
        except Exception as e:
            logger.error(f"Skill injection failed: {e}")

        prompt = f"""Plan the next reactivation touchpoint.
        
- Customer: {customer.first_name}
- Segment: {customer.rfm_segment}
- Purchase History: {customer.total_orders} orders (~${customer.avg_order_value} avg)
- Journey Step: {journey.current_touch}/7
- Past Touches: {len(history)}

{skill_framework}

PAST TOUCHES IN THIS JOURNEY:
{[(h.channel, h.status) for h in history]}

Respond with JSON:
{{
    "channel": "email" or "sms",
    "tone": "warm" or "urgent" or "direct",
    "subject": "Email subject if 'email'",
    "body": "The message body",
    "rationale": "How this fits the 7-Touch Framework",
    "terminate": true/false
}}"""

        try:
            res = await self.router.complete(
                task_type='email_copy',
                system_prompt="You are a Retention Copywriter. Execute the 7-touch framework instructions perfectly.",
                user_prompt=prompt,
                merchant_id=self.merchant_id
            )
            content = res['content'].strip()
            if content.startswith("```"): content = content.split("```")[1]
            if content.startswith("json"): content = content[4:]
            
            plan = json.loads(content.strip())
            
            # Safety checks
            if 'channel' not in plan: plan['channel'] = 'email'
            if 'terminate' not in plan: plan['terminate'] = False
            
            return plan
            
        except Exception as e:
            logger.error(f"Touch generation failed: {e}")
            return {
                "channel": "email",
                "body": "We missed you! Come back and see what's new.",
                "subject": "We miss you",
                "terminate": False
            }

    async def _execute_touch(self, journey: CommercialJourney, customer: Customer, plan: Dict, session):
        """Executes the planned touchpoint."""
        from app.integrations.credentials import get_credential_provider
        from app.integrations.klaviyo import KlaviyoConnector
        from app.integrations.twilio import TwilioConnector

        provider = get_credential_provider()
        channel = plan['channel']
        success = False
        
        if channel == 'sms' and customer.sms_optin:
            creds = await provider.get_credentials(self.merchant_id, 'twilio')
            if creds:
                twilio = TwilioConnector(f"{creds['sid']}:{creds['token']}")
                success = await twilio.send_transactional(customer.phone, "", plan['body'])
        
        elif channel == 'email' and customer.email_optin:
            creds = await provider.get_credentials(self.merchant_id, 'klaviyo')
            if creds:
                klaviyo = KlaviyoConnector(creds['api_key'])
                success = await klaviyo.send_transactional(customer.email, plan['subject'], plan['body'])

        # [SECURE REFACTOR] Report result to Internal API
        await self._authenticate()
        if self._api_token:
             import aiohttp
             headers = {"Authorization": f"Bearer {self._api_token}"}
             async with aiohttp.ClientSession() as http:
                await http.post(
                    "http://localhost:8000/internal/agents/reactivation/journey/touch",
                    json={
                        "journey_id": journey.id,
                        "channel": channel,
                        "content": plan['body'],
                        "status": 'sent' if success else 'failed'
                    },
                    headers=headers
                )

        await self._log_thought(
            thought_type="execution",
            summary=f"Sent {channel} touch to {customer.first_name} ({plan['tone']} tone).",
            detailed_reasoning=plan,
            customer_id=customer.id
        )
