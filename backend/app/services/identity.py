from dataclasses import dataclass
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import AgentClient
import uuid
import logging

logger = logging.getLogger(__name__)

@dataclass
class AgentContext:
    """
    Represents the identity of an autonomous agent.
    Passed through service layers to ensure forensic traceability.
    """
    merchant_id: str
    agent_type: str
    client_id: str
    client_secret_hash: Optional[str] = None

class IdentityService:
    """
    Manages agent identities and credentials.
    Ensures every agent has a valid 'passport' (AgentContext) for its actions.
    """
    
    def __init__(self, db: AsyncSession, merchant_id: str):
        self.db = db
        self.merchant_id = merchant_id

    async def get_or_create_agent_identity(self, agent_type: str) -> AgentContext:
        """
        Retrieves the credentials for a specific agent type.
        If they don't exist, they are created (lazy provisioning).
        """
        # 1. Try to find existing client
        result = await self.db.execute(
            select(AgentClient).where(
                AgentClient.merchant_id == self.merchant_id,
                AgentClient.agent_type == agent_type
            )
        )
        client = result.scalar_one_or_none()

        # 2. Lazy Create if missing
        if not client:
            logger.info(f"🆔 Provisioning new identity for agent: {agent_type}")
            client_id = f"agent_{agent_type}_{uuid.uuid4().hex[:8]}"
            # In a real system, generate a strong random secret and hash it
            secret = uuid.uuid4().hex 
            
            # [HARDENING]: Store secret in TokenVault as well
            from app.services.token_vault import TokenVaultService
            vault = TokenVaultService(self.merchant_id)
            await vault.store_token(
                provider=f"agent_secret_{agent_type}",
                access_token=secret,
                connection_name=f"Internal Agent Identity: {agent_type}"
            )
            
            # Define Default Scopes per Agent Type
            initial_scopes = []
            if agent_type == "observer":
                initial_scopes = ["inventory:update"]
            elif agent_type == "matchmaker":
                initial_scopes = ["matchmaker:update", "proposals:write"]
            elif agent_type == "execution":
                initial_scopes = ["campaigns:execute"]
            
            client = AgentClient(
                merchant_id=self.merchant_id,
                client_id=client_id,
                client_secret_hash=secret, # Vaulted above
                agent_type=agent_type,
                is_active=True,
                allowed_scopes=initial_scopes
            )
            self.db.add(client)
            await self.db.commit() # Commit to persist identity
            await self.db.refresh(client)

        return AgentContext(
            merchant_id=self.merchant_id,
            agent_type=client.agent_type,
            client_id=client.client_id,
            client_secret_hash=client.client_secret_hash
        )

    async def get_agent_credentials(self, agent_type: str) -> Optional[dict]:
        """
        Retrieves agent credentials, preferring TokenVault for the secret.
        """
        from app.services.token_vault import TokenVaultService
        vault = TokenVaultService(self.merchant_id)
        
        # 1. Try to find existing client record
        result = await self.db.execute(
            select(AgentClient).where(
                AgentClient.merchant_id == self.merchant_id,
                AgentClient.agent_type == agent_type
            )
        )
        client = result.scalar_one_or_none()
        
        if not client:
            # Provision if missing
            ctx = await self.get_or_create_agent_identity(agent_type)
            client_id = ctx.client_id
        else:
            client_id = client.client_id

        # 2. Try to get secret from Vault
        secret = await vault.get_access_token(f"agent_secret_{agent_type}")
        
        # 3. Fallback to DB (for migration compatibility)
        if not secret and client:
            secret = client.client_secret_hash
            
        if not secret:
            # Last resort: common demo defaults if we're in a bootstrap state
            defaults = {
                "observer": "secret123",
                "strategy": "secret123",
                "matchmaker": "secret_match_123",
                "execution": "secret123",
                "reactivation": "secret_react_123",
                "seasonal": "secret_season_123"
            }
            secret = defaults.get(agent_type, "secret123")

        return {
            "client_id": client_id,
            "client_secret": secret
        }

    async def authenticate_agent(self, client_id: str, client_secret: str) -> Optional[AgentContext]:
        """
        Verifies agent credentials (M2M Auth).
        Returns AgentContext if valid, enabling JWT issuance.
        """
        result = await self.db.execute(
            select(AgentClient).where(AgentClient.client_id == client_id)
        )
        client = result.scalar_one_or_none()
        
        if not client or not client.is_active:
            return None
            
        # In production, verify hash. For MVP demo, direct compare (as per lazy provision)
        # Note: In real implementation, use verify_password(secret, client.client_secret_hash)
        if client.client_secret_hash != client_secret: 
            return None
            
        return AgentContext(
            merchant_id=client.merchant_id,
            agent_type=client.agent_type,
            client_id=client.client_id
        )
