# app/agents/execution.py
"""
Execution Agent
==============
Handles the actual execution of clearance campaigns through external providers.

World-Class Upgrades:
- Platform Agnostic Execution (Adapter Pattern)
- Predictive Execution (Simulation)
- Adaptive Throttling (Waterfall Memory)
- Self-Verification & Failure Reflection
"""

import os
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Callable, Optional

from sqlalchemy import select
from app.database import async_session_maker
from app.models import (
    InboxItem, Campaign, Merchant, Product, 
    Customer, AuditLog, TouchLog
)

from app.integrations.klaviyo import KlaviyoConnector
from app.integrations.twilio import TwilioConnector
from app.services.waterfall import WaterfallService
from app.integrations.credentials import get_credential_provider
from app.services.governance import GovernanceService
from app.services.inbox import InboxService
from app.services.safety import SafetyService

from app.adapters.registry import AdapterRegistry  # [REFACTOR] New Adapter Registry

logger = logging.getLogger(__name__)

# Custom exceptions
class RetryableError(Exception): pass
class RateLimitError(RetryableError):
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after
class TokenExpiredError(RetryableError): pass
class PermanentError(Exception): pass
class MaxRetriesExceededError(Exception): pass

class ExecutionAgent:
    """
    World-Class Execution Agent.
    """
    
    MAX_RETRIES = 3
    BASE_DELAY = 2
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self.agent_type = "execution"
        self._api_token = None
        self.client_id = f"agent_{self.agent_type}_88b1" # Deterministic ID
        
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
            "product_id": kwargs.get("detailed_reasoning", {}).get("product_id")
        }
        
        try:
            async with aiohttp.ClientSession() as http:
                await http.post(
                    "http://localhost:8000/internal/agents/thoughts",
                    json=payload,
                    headers=headers
                )
        except Exception as e:
            logger.error(f"Failed to log thought via API: {e}")
        
    async def _authenticate(self):
        """[HARDENING] Authenticates with Internal API using Vaulted Credentials."""
        if self._api_token: return
        import aiohttp
        from app.services.identity import IdentityService
        from app.database import async_session_maker
        async with async_session_maker() as db:
            identity_service = IdentityService(db, self.merchant_id)
            creds = await identity_service.get_agent_credentials("execution")
        if not creds:
             logger.error("Failed to fetch Execution credentials")
             return
        async with aiohttp.ClientSession() as http:
            async with http.post("http://localhost:8000/internal/agents/auth", json=creds) as resp:
                if resp.status == 200:
                     self._api_token = (await resp.json())['access_token']
                else:
                     logger.error(f"Execution Agent Auth Failed: {await resp.text()}")

    async def execute_campaign(self, proposal_id: str) -> dict:
        """
        Executes an approved proposal with reasoning-based resilience.
        """
        # 0. SAFETY: Check for Emergency Pause
        safety = SafetyService(self.merchant_id)
        if await safety.is_paused():
            summary = "🛑 [Safety] Execution blocked: Emergency Pause is ACTIVE"
            logger.error(summary)
            await self._mark_campaign_failed(proposal_id, "Emergency Pause is Active")
            return {'status': 'blocked', 'reason': 'safety_pause'}

        # 1. PREDICT: Simulation
        simulation = await self._simulate_execution(proposal_id)
        if simulation.get('blocked', False):
            summary = f"🚫 [Execution] Simulation blocked: {simulation['reason']}"
            logger.warning(summary)
            await self._mark_campaign_failed(proposal_id, simulation['reason'])
            return {'status': 'blocked', 'reason': simulation['reason']}

        # 2. AUTHORIZE: CIBA check
        if await self._requires_async_auth(proposal_id, simulation):
            auth_result = await self._request_ciba_authorization(proposal_id, simulation)
            if auth_result['status'] != 'approved':
                return {'status': 'authorization_' + auth_result['status'], 'reason': f"Merchant {auth_result['status']} the operation"}

        # 3. ACT: Execution with adaptive retries
        retry_count = 0
        last_error = None
        while retry_count < self.MAX_RETRIES:
            try:
                result = await self._execute_campaign_internal(proposal_id, simulation, retry_count)
                return result
            except RateLimitError as e:
                await asyncio.sleep(e.retry_after)
                retry_count += 1
                last_error = e
            except RetryableError as e:
                delay = (self.BASE_DELAY ** (retry_count + 1)) + 1
                await asyncio.sleep(delay)
                retry_count += 1
                last_error = e
            except Exception as e:
                await self._mark_campaign_failed(proposal_id, str(e))
                raise
        
        error_msg = f"Max retries exceeded. Last: {last_error}"
        await self._mark_campaign_failed(proposal_id, error_msg)
        raise MaxRetriesExceededError(error_msg)

    async def _execute_campaign_internal(self, proposal_id: str, simulation: Dict, retry_count: int = 0) -> dict:
        """Internal execution logic using Internal API for locking."""
        if not self._api_token: await self._authenticate()
        import aiohttp
        headers = {"Authorization": f"Bearer {self._api_token}"}
        
        async with aiohttp.ClientSession() as http:
            async with http.post("http://localhost:8000/internal/agents/campaigns/lock", json={"proposal_id": proposal_id}, headers=headers) as resp:
                if resp.status != 200:
                    err = await resp.json()
                    if "already in status" in str(err): return {'status': 'already_executed', 'proposal_id': proposal_id}
                    raise PermanentError(f"Failed to lock proposal: {err}")
                lock_data = await resp.json()
                proposal_data = lock_data['proposal']
                origin_execution_id = lock_data.get('origin_id')
        
        # [REFACTOR] Platform Agnostic Pricing Update
        from decimal import Decimal
        
        async with async_session_maker() as session:
            data = proposal_data
            product_id = data.get('product_id')
            product_title = data.get('product_title', 'Unknown Product')
            strategy_name = data.get('strategy', 'flash_sale')
            copy_data = data.get('copy', {})
            audience = data.get('audience', {})
            discount_percent = float(data.get('discount', 0.0))
            
            # 1. Fetch Context (Merchant & Product)
            # We need explicit merchant object for adapter context
            merchant = (await session.execute(select(Merchant).where(Merchant.id == self.merchant_id))).scalar_one()
            
            prod_res = await session.execute(select(Product).where(Product.id == product_id, Product.merchant_id == self.merchant_id))
            product = prod_res.scalar_one_or_none()
            
            # Inventory Check
            from app.services.shadow_inventory import ShadowInventory
            if product:
                available = ShadowInventory(self.merchant_id).get_available_quantity(f"prod_{product.id}", product.total_inventory)
                if available < 5:
                     await self._report_completion(proposal_id, 'failed', {'failure_reason': 'insufficient_inventory'})
                     return {'status': 'failed', 'reason': 'insufficient_inventory'}

            # 2. ROUTING & EXECUTION
            # Decides where inventory goes based on rules
            from app.channels.router import ChannelRouter
            from app.channels.registry import ChannelRegistry
            import asyncio
            
            router = ChannelRouter(merchant)
            
            # Construct proposal dict for router
            proposal_dict = {
                "proposed_price": Decimal(str(new_price)) if 'new_price' in locals() else Decimal(str(product.cost_price)) * Decimal("1.2"), # Fallback
                "duration_days": 7 # Default
            }
            # Calculate price if not already done
            if product and discount_percent > 0:
                 # Fetch one variant to update (simplification for single-variant products common in clearance)
                from app.models import ProductVariant
                var_res = await session.execute(select(ProductVariant).where(ProductVariant.product_id == product.id))
                variant = var_res.scalars().first()
                if variant:
                    original_price = Decimal(variant.price)
                    new_price = original_price * Decimal(1 - discount_percent)
                    proposal_dict["proposed_price"] = new_price
            
            # Normalize product dict for router
            product_dict = {
                "stock_quantity": product.total_inventory,
                "days_since_last_sale": 30, # TODO: real metric
                "category": product.product_type,
                "product_type": product.product_type,
                "platform_product_id": product.shopify_product_id if product else "",
                "platform_variant_id": variant.shopify_variant_id if variant else "",
                "title": product.title,
                "description": product.title, # Fallback
                "image_url": "https://placeholder.com/img" # Real impl needs image from Product model
            }
            
            routing = router.route(product_dict, proposal_dict)
            results = {"store": None, "external": []}
            
            # --- STEP 3A: Execute on merchant's store (Channel A) ---
            if routing["store"] and product and variant:
                try:
                    adapter = AdapterRegistry.get_adapter(merchant.platform)
                    merchant_context = merchant.platform_context or {}
                    
                    # Update price on store
                    res = await adapter.update_price(
                        merchant_context=merchant_context,
                        platform_product_id=product.shopify_product_id,
                        platform_variant_id=variant.shopify_variant_id, 
                        new_price=new_price
                    )
                    
                    if not res.success:
                         await self._report_completion(proposal_id, 'failed', {'failure_reason': f"Store update failed: {res.error_message}"})
                         return {'status': 'failed', 'reason': 'store_update_failed'}
                         
                    results["store"] = {"success": True}
                    
                    await self._log_thought(
                        thought_type="action", 
                        summary=f"Updated price to {new_price} on {merchant.platform}",
                        product_id=product.id
                    )
                except Exception as e:
                    logger.error(f"Store price update failed: {e}")
                    await self._report_completion(proposal_id, 'failed', {'failure_reason': f"Price update failed: {str(e)}"})
                    return {'status': 'failed', 'reason': 'price_update_failed'}

            # --- STEP 3B: Execute on external channels (Channel B/C) — parallel ---
            async def _list_on_channel(channel_info: Dict):
                try:
                    ch_name = channel_info["channel"]
                    channel = ChannelRegistry.get_channel(ch_name)
                    # Get credentials safely
                    creds = (merchant.external_channel_credentials or {}).get(ch_name, {})
                    
                    return await channel.create_listing(
                        channel_context=creds,
                        product=product_dict,
                        price=channel_info["price"],
                        quantity=channel_info["allocated_units"],
                        duration_days=channel_info["duration_days"],
                    )
                except Exception as e:
                    return e

            if routing.get("external_channels") and product:
                external_tasks = [_list_on_channel(ch) for ch in routing["external_channels"]]
                external_results = await asyncio.gather(*external_tasks, return_exceptions=True)
                
                for ch_info, result in zip(routing["external_channels"], external_results):
                    if isinstance(result, Exception) or (hasattr(result, 'success') and not result.success):
                         err = str(result) if isinstance(result, Exception) else result.error_message
                         results["external"].append({
                            "channel": ch_info["channel"],
                            "success": False,
                            "error": err
                        })
                         logger.error(f"Failed to list on {ch_info['channel']}: {err}")
                    else:
                        results["external"].append({
                            "channel": ch_info["channel"],
                            "success": True,
                            "listing_id": result.external_listing_id
                        })
                        await self._log_thought(
                            thought_type="action", 
                            summary=f"Listed on {ch_info['channel']} (ID: {result.external_listing_id})",
                            product_id=product.id
                        )

            # --- SCHEDULE CLEANUP ---
            # If external listings created, schedule cleanup task
            successful_listings = [r for r in results["external"] if r["success"]]
            if successful_listings:
                from app.tasks.channels import cleanup_external_listings
                # Campaign duration
                duration_days = proposal_dict.get("duration_days", 7)
                cleanup_eta = datetime.utcnow() + asyncio.timedelta(days=duration_days)
                
                # Note: Passing campaign_id which is created in next block. 
                # Ideally we create campaign record FIRST then execute.
                # Refactor: We will use proposal_id or defer scheduling to after campaign creation.
                # For now, we will add 'cleanup_needed' flag to campaign creation metadata

            # 3. Create Campaign Record
            async with aiohttp.ClientSession() as http:
                 async with http.post("http://localhost:8000/internal/agents/campaigns/create", json={"name": f"Clearance: {product_title}", "type": strategy_name, "product_ids": [product_id] if product_id else [], "target_segments": audience.get('segments', []), "content_snapshot": copy_data, "origin_execution_id": origin_execution_id, "status": 'active'}, headers=headers) as resp:
                     if resp.status == 200:
                          campaign_id = (await resp.json())['id']
            
            from types import SimpleNamespace
            campaign = SimpleNamespace(id=campaign_id, name=f"Clearance: {product_title}", target_segments=audience.get('segments', []))
            
            idempotency_key = f"{proposal_id}:{retry_count}"
            klaviyo_res = await self._execute_klaviyo(merchant, campaign, copy_data, product_title, session, simulation, idempotency_key)
            twilio_res = await self._execute_twilio(merchant, campaign, copy_data, product_title, session, simulation, proposal_id, retry_count)

            klaviyo_success = klaviyo_res['success']
            twilio_success = twilio_res['success']
            final_status = 'executed' if (klaviyo_success or twilio_success) else 'failed'
            
            await self._report_completion(proposal_id, final_status, proposal_data)
            verification = await self._verify_execution(campaign, klaviyo_success, twilio_success, origin_execution_id)
            
            return {'status': 'success' if (klaviyo_success or twilio_success) else 'partial_failure', 'campaign_id': campaign.id, 'klaviyo': klaviyo_success, 'twilio': twilio_success, 'verification': verification}

    async def _report_completion(self, proposal_id, status, details):
        """Reports execution results to the Internal API."""
        if not self._api_token: await self._authenticate()
        import aiohttp
        headers = {"Authorization": f"Bearer {self._api_token}"}
        async with aiohttp.ClientSession() as http:
            await http.post("http://localhost:8000/internal/agents/campaigns/complete", json={"proposal_id": proposal_id, "status": status, "details": details}, headers=headers)

    async def _simulate_execution(self, proposal_id: str) -> Dict:
        """Predictive execution simulation."""
        from app.services.llm_router import LLMRouter
        from app.services.memory import MemoryService
        router = LLMRouter()
        memory = MemoryService(self.merchant_id)
        recent_events = await memory.recall_thoughts(agent_type="execution", limit=5)
        prompt = f"Reason about execution risk for proposal {proposal_id}."
        try:
            res = await router.complete(task_type="strategy_generation", system_prompt="Execution Strategist", user_prompt=prompt, merchant_id=self.merchant_id)
            content = res['content'].strip()
            if '```' in content: content = content.split('```')[1].replace('json', '')
            return json.loads(content)
        except:
            return {"blocked": False, "stagger_required": False, "batch_size": 20, "stagger_delay_seconds": 5}

    async def _execute_klaviyo(self, merchant, campaign, copy, title, session, simulation, idempotency_key) -> Dict:
        provider = get_credential_provider()
        creds = await provider.get_credentials(self.merchant_id, 'klaviyo')
        if not creds: return {'success': False, 'reason': 'missing_credentials'}
        try:
            klaviyo = KlaviyoConnector(creds['api_key'])
            res = await klaviyo.create_campaign(name=campaign.name, subject=copy.get('email_subject', f'Deal: {title}'), body_html=copy.get('email_body', f'Check out {title}'), target_segment_ids=campaign.target_segments or ["DEAL_HUNTERS"], idempotency_key=idempotency_key)
            if not self._api_token: await self._authenticate()
            headers = {"Authorization": f"Bearer {self._api_token}"}
            async with aiohttp.ClientSession() as http:
                await http.post("http://localhost:8000/internal/agents/campaigns/log", json={"campaign_id": campaign.id, "channel": "email", "external_id": res.get('id'), "status": "sent"}, headers=headers)
            return {'success': True}
        except Exception as e: return {'success': False, 'reason': str(e)}

    async def _execute_twilio(self, merchant, campaign, copy, title, session, simulation, proposal_id, retry_count) -> Dict:
        provider = get_credential_provider()
        creds = await provider.get_credentials(self.merchant_id, 'twilio')
        if not creds: return {'success': False, 'reason': 'missing_credentials'}
        try:
            stmt = select(Customer).where(Customer.merchant_id == self.merchant_id, Customer.sms_optin == True, Customer.rfm_segment.in_(campaign.target_segments or []))
            customers = (await session.execute(stmt)).scalars().all()
            if not customers: return {'success': False, 'reason': 'no_eligible_customers'}
            twilio = TwilioConnector(f"{creds['sid']}:{creds['token']}")
            sms_body = copy.get('sms_body', f'Deal on {title}!')
            async def send_wrapper(customer):
                try: 
                    res = await twilio.send_transactional(customer.phone, "", sms_body, idempotency_key=f"{proposal_id}:{customer.id}:{retry_count}")
                    if res and res.get('id'):
                        if not self._api_token: await self._authenticate()
                        headers = {"Authorization": f"Bearer {self._api_token}"}
                        async with aiohttp.ClientSession() as http:
                            await http.post("http://localhost:8000/internal/agents/campaigns/log", json={"campaign_id": campaign.id, "channel": "sms", "external_id": res.get('id'), "status": "sent", "customer_id": customer.id}, headers=headers)
                except: pass
            await WaterfallService(batch_size=simulation.get('batch_size', 20), delay_seconds=simulation.get('stagger_delay_seconds', 5)).execute_waterfall(customers, send_wrapper)
            return {'success': True}
        except Exception as e: return {'success': False, 'reason': str(e)}

    async def _verify_execution(self, campaign, klaviyo_success, twilio_success, execution_id: Optional[str] = None):
        verified = klaviyo_success or twilio_success
        await self._log_thought(thought_type="verification", summary=f"Execution {'verified ✅' if verified else 'issues ⚠️'}", detailed_reasoning={'klaviyo': klaviyo_success, 'twilio': twilio_success}, execution_id=execution_id)
        return {'verified': verified, 'issues': [] if verified else ["No channels delivered"]}

    async def _mark_campaign_failed(self, proposal_id: str, reason: str):
        async with async_session_maker() as session:
            p = (await session.execute(select(InboxItem).where(InboxItem.id == proposal_id, InboxItem.merchant_id == self.merchant_id))).scalar_one_or_none()
            if p:
                p.status = 'failed'
                p.proposal_data = {**(p.proposal_data or {}), 'failure_reason': reason}
                await session.commit()
        await self._notify_merchant_failure(proposal_id, reason)

    async def _notify_merchant_failure(self, proposal_id: str, reason: str):
        if not self._api_token: await self._authenticate()
        headers = {"Authorization": f"Bearer {self._api_token}"}
        async with aiohttp.ClientSession() as http:
             await http.post("http://localhost:8000/internal/agents/notifications/failure", json={"reason": reason, "details": "Execution Agent Failure"}, headers=headers)

    async def _requires_async_auth(self, proposal_id: str, simulation: Dict) -> bool:
        """
        [HARDENED]: CIBA Policy Check.
        Determines if an operation requires explicit human authorization.
        """
        async with async_session_maker() as session:
            # 1. Fetch Proposal & Merchant Context
            proposal = (await session.execute(select(InboxItem).where(InboxItem.id == proposal_id, InboxItem.merchant_id == self.merchant_id))).scalar_one_or_none()
            merchant = (await session.execute(select(Merchant).where(Merchant.id == self.merchant_id))).scalar_one_or_none()
            
            if not proposal or not merchant: return False
            
            data = proposal.proposal_data or {}
            
            # --- POLICY CHECKS ---
            
            # 1. Discount Cap Breach
            # Honors merchant's specific profitability guardrail
            discount_val = data.get('discount', 0)
            if isinstance(discount_val, str): discount_val = float(discount_val.replace('%', '')) / 100
            
            # Default to 40% if not set
            max_auto_discount = float(merchant.max_auto_discount) if merchant.max_auto_discount else 0.40
            if discount_val > max_auto_discount:
                logger.info(f"CIBA Trigger: Discount {discount_val:.0%} > Configured Max {max_auto_discount:.0%}")
                return True
                
            # 2. High Value Spending / Risk
            # Default $500 limit for autonomous ad spend or resource usage
            estimated_cost = simulation.get('estimated_cost', 0)
            max_daily_budget = 500.0  # TODO: Move to Merchant.max_daily_budget
            if estimated_cost > max_daily_budget:
                logger.info(f"CIBA Trigger: Cost ${estimated_cost} > Budget ${max_daily_budget}")
                return True

            # 3. Mass Blast Protection
            # Prevent spamming thousands of users without approval
            audience_size = len(data.get('audience', {}).get('customer_ids', []))
            if audience_size > 2000:
                logger.info(f"CIBA Trigger: Audience {audience_size} > 2000")
                return True

            # 4. "Training Wheels" for New Merchants
            # First 14 days require approval for almost everything
            if merchant.created_at:
                age_days = (datetime.utcnow() - merchant.created_at).days
                if age_days < 14:
                    logger.info(f"CIBA Trigger: New Merchant (Age {age_days} days)")
                    return True

            # 5. AI Risk Flag
            if simulation.get('high_risk', False):
                logger.info("CIBA Trigger: Simulation detected high risk")
                return True
                
            return False

    async def _request_ciba_authorization(self, proposal_id: str, simulation: Dict) -> Dict:
        from app.services.ciba_service import CIBAService
        async with async_session_maker() as session:
            proposal = (await session.execute(select(InboxItem).where(InboxItem.id == proposal_id, InboxItem.merchant_id == self.merchant_id))).scalar_one_or_none()
            data = proposal.proposal_data or {}
            authorization_details = {"type": "campaign_execute", "campaign_name": data.get('product_title', 'Clearance Campaign'), "discount_percentage": data.get('discount', 0), "strategy": data.get('strategy', 'flash_sale'), "estimated_cost": simulation.get('estimated_cost', 0), "estimated_revenue": simulation.get('predicted_revenue', 0), "products": [data.get('product_title', 'Unknown')], "target_customers": len(data.get('audience', {}).get('customer_ids', []))}
        status, details = await CIBAService(self.merchant_id).wait_for_authorization((await CIBAService(self.merchant_id).initiate_authorization(agent_type="execution", operation_type="campaign_execute", authorization_details=authorization_details, inbox_item_id=proposal_id, timeout_seconds=300, notification_channels=["push", "email"])).auth_req_id)
        return {"status": status, "details": details}
