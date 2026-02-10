from datetime import datetime, timedelta
import asyncio
import json
import logging
from typing import Dict, Any, List

from temporalio import activity
from sqlalchemy import select, update
from app.database import async_session_maker
from app.models import (
    InboxItem, Campaign, Merchant, Product, 
    Customer, AuditLog, TouchLog
)
from app.services.safety import SafetyService
from app.services.ciba_service import CIBAService
from app.integrations.credentials import get_credential_provider
from app.integrations.klaviyo import KlaviyoConnector
from app.integrations.twilio import TwilioConnector
from app.services.waterfall import WaterfallService
from app.services.thought_logger import ThoughtLogger
from app.services.inbox import InboxService
from app.services.governance import GovernanceService

logger = logging.getLogger(__name__)

# =============================================================================
# SAFETY & CHECKS
# =============================================================================

@activity.defn
async def check_safety_pause(merchant_id: str) -> bool:
    safety = SafetyService(merchant_id)
    return await safety.is_paused()

@activity.defn
async def mark_campaign_failed(merchant_id: str, proposal_id: str, reason: str):
    async with async_session_maker() as session:
        res = await session.execute(
            select(InboxItem).where(
                InboxItem.id == proposal_id,
                InboxItem.merchant_id == merchant_id
            )
        )
        p = res.scalar_one_or_none()
        if p:
            p.status = 'failed'
            p.proposal_data = {**(p.proposal_data or {}), 'failure_reason': reason}
            
            # Notify merchant
            session.add(InboxItem(
                merchant_id=merchant_id, 
                type="campaign_failure", 
                status="pending", 
                agent_type="execution", 
                confidence=100, 
                proposal_data={"message": f"Execution failed: {reason}"}
            ))
            await session.commit()

# =============================================================================
# SIMULATION & AUTH
# =============================================================================

@activity.defn
async def simulate_execution(merchant_id: str, proposal_id: str) -> Dict:
    # Re-using the LLM Logic from ExecutionAgent (simplified for activity)
    from app.services.llm_router import LLMRouter
    from app.services.memory import MemoryService
    
    router = LLMRouter()
    memory = MemoryService(merchant_id)
    recent_events = await memory.recall_thoughts(agent_type="execution", limit=5)
    
    prompt = f"""Reason about execution risk for proposal {proposal_id}.
Recent History: {[e.summary for e in recent_events]}

Respond with JSON:
{{
    "blocked": false,
    "reason": "",
    "stagger_required": true,
    "stagger_delay_seconds": 10,
    "batch_size": 25,
    "rationale": "Execution simulation rationale"
}}"""
    try:
        res = await router.complete(task_type="strategy_generation", system_prompt="Execution Strategist", user_prompt=prompt, merchant_id=merchant_id)
        content = res['content'].strip()
        if '```' in content: content = content.split('```')[1].replace('json', '')
        return json.loads(content)
    except:
        return {"blocked": False, "stagger_required": False, "batch_size": 20, "stagger_delay_seconds": 5}

@activity.defn
async def check_requires_auth(merchant_id: str, proposal_id: str, simulation: Dict) -> bool:
    # Logic copied from ExecutionAgent._requires_async_auth
    async with async_session_maker() as session:
        result = await session.execute(
            select(InboxItem).where(InboxItem.id == proposal_id, InboxItem.merchant_id == merchant_id)
        )
        proposal = result.scalar_one_or_none()
        if not proposal: return False
        
        data = proposal.proposal_data or {}
        discount = data.get('discount', 0)
        # Parse discount string if needed
        if isinstance(discount, str): discount = float(discount.replace('%', '')) / 100
            
        estimated_cost = simulation.get('estimated_cost', 0)
        audience_size = len(data.get('audience', {}).get('customer_ids', []))
        
        if discount > 0.30: return True
        if estimated_cost > 1000: return True
        if audience_size > 500: return True
        return False

@activity.defn
async def initiate_ciba_auth(merchant_id: str, proposal_id: str, simulation: Dict):
    # Just initiates - does not wait. Workflow handles the wait via Signal or long-polling activity.
    # For now, we assume this sends the push notification.
    pass

# =============================================================================
# EXECUTION (CORE)
# =============================================================================

@activity.defn
async def claim_proposal_execution(merchant_id: str, proposal_id: str) -> Dict:
    async with async_session_maker() as session:
        # Atomic Update
        claim_result = await session.execute(
            update(InboxItem)
            .where(
                InboxItem.id == proposal_id,
                InboxItem.merchant_id == merchant_id,
                InboxItem.status.in_(['approved', 'pending'])
            )
            .values(status='executing')
            .returning(InboxItem)
        )
        proposal = claim_result.scalar_one_or_none()
        
        if not proposal:
             # Check status
            check = await session.execute(select(InboxItem).where(InboxItem.id == proposal_id))
            existing = check.scalar_one_or_none()
            if existing:
                return {'status': 'failed', 'reason': f'Invalid status: {existing.status}'}
            return {'status': 'failed', 'reason': 'Not found'}
            
        await session.commit()
        return {'status': 'success', 'data': proposal.proposal_data}

@activity.defn
async def create_campaign_record(merchant_id: str, proposal_data: Dict) -> str:
    async with async_session_maker() as session:
        product_title = proposal_data.get('product_title', 'Unknown Product')
        strategy_name = proposal_data.get('strategy', 'flash_sale')
        product_id = proposal_data.get('product_id')
        audience = proposal_data.get('audience', {})
        copy_data = proposal_data.get('copy', {})
        
        campaign = Campaign(
            merchant_id=merchant_id,
            name=f"Clearance: {product_title}",
            type=strategy_name,
            status='processing', # distinct from active until channels send
            product_ids=[product_id] if product_id else [],
            target_segments=audience.get('segments', []),
            content_snapshot=copy_data
        )
        session.add(campaign)
        await session.commit()
        return campaign.id

@activity.defn
async def send_klaviyo_campaign(merchant_id: str, campaign_id: str, proposal_data: Dict) -> Dict:
    # Klaviyo Execution Logic
    provider = get_credential_provider()
    creds = await provider.get_credentials(merchant_id, 'klaviyo')
    if not creds: return {'success': False, 'reason': 'missing_credentials'}

    async with async_session_maker() as session:
        # Get campaign name for Klaviyo
        c_res = await session.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = c_res.scalar_one()
        
        copy = proposal_data.get('copy', {})
        title = proposal_data.get('product_title', '')
        
        try:
            klaviyo = KlaviyoConnector(creds['api_key'])
            # Idempotency based on campaign ID
            idempotency_key = f"klaviyo_camp_{campaign_id}" 
            
            res = await klaviyo.create_campaign(
                name=campaign.name,
                subject=copy.get('email_subject', f'Deal: {title}'),
                body_html=copy.get('email_body', f'Check out {title}'),
                target_segment_ids=campaign.target_segments or ["DEAL_HUNTERS"],
                idempotency_key=idempotency_key
            )
            
            # Log
            log = TouchLog(
                merchant_id=merchant_id,
                campaign_id=campaign_id,
                channel='email',
                external_id=res.get('id'),
                status='sent'
            )
            session.add(log)
            await session.commit()
            return {'success': True, 'id': res.get('id')}
            
        except Exception as e:
            logger.error(f"Klaviyo Activity Failed: {e}")
            # Raising exception triggers Temporal Retry Policy
            raise e

@activity.defn
async def send_twilio_campaign(merchant_id: str, campaign_id: str, proposal_data: Dict, simulation: Dict) -> Dict:
    provider = get_credential_provider()
    creds = await provider.get_credentials(merchant_id, 'twilio')
    if not creds: return {'success': False, 'reason': 'missing_credentials'}
    
    async with async_session_maker() as session:
        c_res = await session.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = c_res.scalar_one()
        
        # Get Customers
        stmt = select(Customer).where(
            Customer.merchant_id == merchant_id, 
            Customer.sms_optin == True, 
            Customer.rfm_segment.in_(campaign.target_segments or [])
        )
        res = await session.execute(stmt)
        customers = res.scalars().all()
        if not customers: return {'success': False, 'reason': 'no_eligible_customers'}
        
        twilio = TwilioConnector(f"{creds['sid']}:{creds['token']}")
        sms_body = proposal_data.get('copy', {}).get('sms_body', 'Deal!')
        
        # In a real heavy scenario, we might even split THIS into chunks or child workflows
        # For now, we do the waterfall here. If activity crashes, it retries ALL.
        # To make it truly granular, we'd need an activity per batch or per customer.
        # Keeping as-is for MVP migration (still better than Celery).
        
        async def send_wrapper(customer):
            try:
                # Per-customer idempotency key
                customer_key = f"sms_{campaign_id}_{customer.id}"
                res = await twilio.send_transactional(customer.phone, "", sms_body, idempotency_key=customer_key)
                if res and res.get('id'):
                     # We need session here for TouchLog... complex in async wrapper inside activity
                     # Ideally we just collect results
                     return res.get('id')
            except: pass
            return None

        batch_size = simulation.get('batch_size', 20)
        delay = simulation.get('stagger_delay_seconds', 5)
        
        waterfall = WaterfallService(batch_size=batch_size, delay_seconds=delay)
        # Note: Waterfall service might need slight adaptation if it expects session
        # Use execute_waterfall generic
        await waterfall.execute_waterfall(customers, send_wrapper)
        
        return {'success': True}

@activity.defn
async def verify_and_update_status(merchant_id: str, proposal_id: str, campaign_id: str, klaviyo_res: Dict, twilio_res: Dict) -> Dict:
    async with async_session_maker() as session:
        # Fetch entities
        p_res = await session.execute(select(InboxItem).where(InboxItem.id == proposal_id))
        proposal = p_res.scalar_one()
        
        c_res = await session.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = c_res.scalar_one()
        
        k_success = klaviyo_res.get('success', False)
        t_success = twilio_res.get('success', False)
        
        if k_success or t_success:
            proposal.status = 'executed'
            proposal.executed_at = datetime.utcnow()
            campaign.status = 'active'
            
            # Log Action
            inbox_service = InboxService(session, merchant_id)
            await inbox_service._log_action("Execute", "Campaign", campaign.id, {"proposal_id": proposal_id})
            
        else:
            proposal.status = 'failed'
            campaign.status = 'failed'
            
        await session.commit()
        
        return {
            'status': 'success' if (k_success or t_success) else 'failed',
            'campaign_id': campaign_id
        }
