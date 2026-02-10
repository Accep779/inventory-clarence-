import asyncio
import hashlib
from sqlalchemy import select
from app.database import async_session_maker
from app.models import AgentClient

async def seed_agents():
    async with async_session_maker() as session:
        # 1. Matchmaker
        match_id = "agent_matchmaker_match_v1"
        match_secret = "secret_match_123"
        
        print(f"Seeding {match_id}...")
        existing = await session.execute(select(AgentClient).where(AgentClient.client_id == match_id))
        if not existing.scalar_one_or_none():
            client = AgentClient(
                merchant_id="merchant_01", # Assuming default demo merchant
                client_id=match_id,
                client_secret_hash=match_secret, # Using raw for demo consistency
                agent_type="matchmaker",
                is_active=True,
                allowed_scopes=["matchmaker:update", "proposals:write"]
            )
            session.add(client)
        
        # 2. Reactivation
        react_id = "agent_reactivation_react_v1"
        react_secret = "secret_react_123"
        
        print(f"Seeding {react_id}...")
        existing = await session.execute(select(AgentClient).where(AgentClient.client_id == react_id))
        if not existing.scalar_one_or_none():
            client = AgentClient(
                merchant_id="merchant_01",
                client_id=react_id,
                client_secret_hash=react_secret,
                agent_type="reactivation",
                is_active=True,
                allowed_scopes=["reactivation:execute"]
            )
            session.add(client)
            
        await session.commit()
        print("✅ Agents seeded successfully.")

if __name__ == "__main__":
    asyncio.run(seed_agents())
