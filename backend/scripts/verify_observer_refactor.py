import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), ".."))

from app.database import async_session_maker
from app.models import Merchant, Product, AgentClient
from sqlalchemy import select
from app.agents.observer import ObserverAgent
from unittest.mock import MagicMock, patch

async def verify_observer_refactor():
    print("\nDetectors On... 🕵️ Testing Observer Agent Refactor...")
    
    # Needs Mock for Memory/LLM to run in isolation
    with patch('app.agents.observer.MemoryService'), \
         patch('app.agents.observer.LLMRouter'), \
         patch('app.agents.observer.InventoryClusteringService'), \
         patch('app.agents.observer.MemoryStreamService'):
         
        async with async_session_maker() as session:
            # 1. Setup Context
            result = await session.execute(select(Merchant).limit(1))
            merchant = result.scalar_one_or_none()
            if not merchant:
                 print("❌ No merchant found")
                 return

            # 2. Provision Identity for Observer (if missing)
            from app.services.identity import IdentityService
            identity = IdentityService(session, merchant.id)
            ctx = await identity.get_or_create_agent_identity("observer")
            
            # Ensure it has scope
            stmt = select(AgentClient).where(AgentClient.client_id == ctx.client_id)
            client = (await session.execute(stmt)).scalar_one()
            client.allowed_scopes = ["inventory:update"]
            client.client_secret_hash = "secret123" 
            await session.commit()
            print(f"✅ Observer Identity Configured: {ctx.client_id}")

            # 3. Create or Fetch a Product to Observe
            prod_res = await session.execute(select(Product).limit(1))
            product = prod_res.scalar_one_or_none()
            if not product:
                print("❌ No product found to observe")
                return
            
            print(f"✅ Observing Product: {product.title} (Current DeadStock: {product.is_dead_stock})")
            
            # 4. Run Observer Agent (Brain)
            agent = ObserverAgent(merchant.id)
            # Patch deterministic ID 
            agent.client_id = ctx.client_id 
            
            # Create a fake analysis result
            analysis_result = [{
                "id": product.id,
                "velocity_score": 10.5,
                "is_dead_stock": True,
                "severity": "high",
                "days_since_last_sale": 100
            }]
            
            print("🚀 Triggering Batch Update via API...")
            try:
                # This should:
                # 1. Authenticate
                # 2. POST /inventory/status
                await agent.batch_update_status(analysis_result)
                print("✅ Batch Update Call Completed.")
                
                # 5. Verify DB State Changed
                await session.refresh(product)
                if product.is_dead_stock and product.dead_stock_severity == "high":
                    print("✅ Verification Success: Product updated in DB via API!")
                else:
                    print(f"❌ Verification Failed: Product state mismatch. DeadStock: {product.is_dead_stock}")
                    
            except Exception as e:
                print(f"❌ Update Failed: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_observer_refactor())
