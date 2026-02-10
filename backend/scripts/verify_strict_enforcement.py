import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), ".."))

from app.database import async_session_maker
from app.models import Merchant, AgentClient
from sqlalchemy import select
from app.auth_middleware import create_agent_token
from uuid import uuid4

async def verify_strict_scopes():
    print("\n🛡️ Testing Strict Scope Enforcement...")
    
    async with async_session_maker() as session:
        # 1. Get a merchant
        result = await session.execute(select(Merchant).limit(1))
        merchant = result.scalar_one_or_none()
        if not merchant:
             print("❌ No merchant found")
             return

        # 2. Mint a "Weak Token" (No Scopes)
        token_data = {
            "client_id": "weak_agent",
            "agent_type": "outsider",
            "merchant_id": merchant.id,
            "scopes": [] # EMPTY SCOPES
        }
        token = create_agent_token(token_data)
        print("✅ Minted Weak Token (No Scopes)")
        
        # 3. Try to access PROTECTED resources
        import aiohttp
        headers = {"Authorization": f"Bearer {token}"}
        
        async with aiohttp.ClientSession() as http:
            # Test A: Create Proposal (Requires proposals:write)
            print("🔸 Intentional Fail Test: POST /internal/agents/proposals")
            async with http.post(
                "http://localhost:8000/internal/agents/proposals",
                json={"title": "Hacked Proposal", "description": "Fail", "pricing": {}, "strategy": "fail"},
                headers=headers
            ) as resp:
                if resp.status == 403:
                    print("✅ BLOCKED (403 Forbidden) - Success!")
                else:
                    print(f"❌ FAILED! Security Hole. Status: {resp.status}")

            # Test B: Lock Campaign (Requires campaigns:execute)
            print("🔸 Intentional Fail Test: POST /internal/agents/campaigns/lock")
            async with http.post(
                "http://localhost:8000/internal/agents/campaigns/lock",
                json={"proposal_id": str(uuid4())},
                headers=headers
            ) as resp:
                if resp.status == 403:
                    print("✅ BLOCKED (403 Forbidden) - Success!")
                else:
                     print(f"❌ FAILED! Security Hole. Status: {resp.status}")
                     
            # Test C: Inventory Update (Requires inventory:update)
            print("🔸 Intentional Fail Test: POST /internal/agents/inventory/status")
            async with http.post(
                "http://localhost:8000/internal/agents/inventory/status",
                json={"updates": []},
                headers=headers
            ) as resp:
                if resp.status == 403:
                    print("✅ BLOCKED (403 Forbidden) - Success!")
                else:
                     print(f"❌ FAILED! Security Hole. Status: {resp.status}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_strict_scopes())
