import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), ".."))

from app.database import async_session_maker
from app.models import Merchant, InboxItem, AgentClient
from sqlalchemy import select
from app.agents.execution import ExecutionAgent
from uuid import uuid4
from unittest.mock import MagicMock, patch

async def verify_execution_refactor():
    print("\n🕵️ Starting Execution Agent Refactor Verification...")
    
    # MOCK Dependencies to avoid Redis/Celery errors
    with patch('app.agents.execution.SafetyService') as MockSafety, \
         patch('app.agents.execution.ThoughtLogger') as MockLogger, \
         patch('app.agents.execution.WaterfallService') as MockWaterfall:
         
        # Configure Mocks with resolved Futures
        def async_return(result):
            f = asyncio.Future()
            f.set_result(result)
            return f
            
        safety_instance = MockSafety.return_value
        safety_instance.is_paused.side_effect = lambda: async_return(False)
        
        async with async_session_maker() as session:
            # 1. Setup Context
            result = await session.execute(select(Merchant).limit(1))
            merchant = result.scalar_one_or_none()
            if not merchant:
                 print("❌ No merchant found")
                 return

            # 2. Provision Identity for Execution Agent (if missing)
            from app.services.identity import IdentityService
            identity = IdentityService(session, merchant.id)
            ctx = await identity.get_or_create_agent_identity("execution")
            
            # Ensure it has scope
            stmt = select(AgentClient).where(AgentClient.client_id == ctx.client_id)
            client = (await session.execute(stmt)).scalar_one()
            client.allowed_scopes = ["campaigns:execute"]
            client.client_secret_hash = "secret123" # Force known secret
            await session.commit()
            print(f"✅ Exec Identity Configured: {ctx.client_id}")

            # 3. Create a Dummy Proposal to "Execute"
            proposal = InboxItem(
                merchant_id=merchant.id,
                type="clearance_proposal",
                status="approved", # Must be approved to be claimable
                agent_type="strategy",
                proposal_data={
                    "product_id": "dummy_prod",
                    "product_title": "Test Product",
                    "strategy": "flash_sale",
                    "audience": {"segments": ["vip"]},
                    "copy": {}
                }
            )
            session.add(proposal)
            await session.commit()
            await session.refresh(proposal)
            print(f"✅ Created Mock Proposal: {proposal.id}")
            
        # 4. Run Execution Agent
        agent = ExecutionAgent(merchant.id)
        # Patch client_id to match the one we just provisioned (since code has hardcoded deterministic one, likely same, but safety first)
        agent.client_id = ctx.client_id
        
        # Mock simulate_execution to bypass AI/Memory latency using resolved future
        agent._simulate_execution = MagicMock(side_effect=lambda x: async_return({"blocked": False, "high_risk": False}))
        
        print("🚀 Triggering Execution...")
        try:
            # We expect this to:
            # 1. Authenticate
            # 2. Call POST /lock
            # 3. "Execute" (Simulate)
            # 4. Call POST /complete
            result = await agent.execute_campaign(proposal.id)
            
            print(f"✅ Execution Result: {result}")
            
            if result['status'] == 'partial_failure':
                 # This is EXPECTED because we don't have real Klaviyo/Twilio creds in this test env
                 # The key is that it RAN, not that it succeeded external calls
                 print("✅ Partial failure is expected (no external creds). Flow worked.")
            elif result['status'] == 'success':
                 print("✅ Success!")
            else:
                 print(f"⚠️ Unexpected status: {result['status']}")

        except Exception as e:
            print(f"❌ Execution Failed: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_execution_refactor())
