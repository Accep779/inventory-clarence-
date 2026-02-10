import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), ".."))

from app.database import async_session_maker
from app.services.identity import IdentityService
from app.models import Merchant, AgentClient
from sqlalchemy import select
import aiohttp

API_URL = "http://localhost:8000/internal/agents"

async def setup_test_data():
    """Provisions a test merchant and strategy agent."""
    async with async_session_maker() as session:
        # 1. Get or Create Merchant
        result = await session.execute(select(Merchant).limit(1))
        merchant = result.scalar_one_or_none()
        if not merchant:
            print("❌ No merchant found. Run the app setup first.")
            return None, None
            
        # 2. Get or Create Agent Identity (Strategy)
        identity_service = IdentityService(session, merchant.id)
        # Note: In real app we'd use a fixed CLI command, here using service method
        # We need to manually set scopes for the test
        ctx = await identity_service.get_or_create_agent_identity("strategy")
        
        # Update scopes for test
        stmt = select(AgentClient).where(AgentClient.client_id == ctx.client_id)
        client = (await session.execute(stmt)).scalar_one()
        client.allowed_scopes = ["proposals:write", "inventory:read"]
        client.client_secret_hash = "secret123" # Force known secret for test
        await session.commit()
        
        print(f"✅ Setup Agent: {ctx.client_id}")
        return ctx.client_id, "secret123"

async def test_auth_flow(client_id, client_secret):
    """Effective 'Integration Test' for the new Auth System."""
    async with aiohttp.ClientSession() as session:
        # 1. Authenticate (Login)
        print(f"\n🔐 Attempting Login for {client_id}...")
        async with session.post(f"{API_URL}/auth", json={
            "client_id": client_id,
            "client_secret": client_secret
        }) as resp:
            if resp.status != 200:
                print(f"❌ Login Failed: {await resp.text()}")
                return
            
            data = await resp.json()
            token = data['access_token']
            print("✅ Login Success! Token acquired.")
            
        # 2. Use Protected Endpoint (Create Proposal)
        print("\n📝 Creating Proposal as Agent...")
        headers = {"Authorization": f"Bearer {token}"}
        proposal = {
            "title": "Auth Test Proposal",
            "description": "Created via Internal API",
            "pricing": {"original": 100, "sale": 80},
            "strategy": "test_strategy"
        }
        
        async with session.post(f"{API_URL}/proposals", json=proposal, headers=headers) as resp:
            if resp.status == 200:
                print(f"✅ Proposal Created: {await resp.json()}")
            else:
                print(f"❌ Proposal Creation Failed: {await resp.text()}")

'''        
        # 3. Test Invalid Scope (Negative Test)
        # (Optional: Would require a different agent without scope)
'''

if __name__ == "__main__":
    # Windows Selector Policy fix
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    loop = asyncio.get_event_loop()
    client_id, secret = loop.run_until_complete(setup_test_data())
    if client_id:
        loop.run_until_complete(test_auth_flow(client_id, secret))
