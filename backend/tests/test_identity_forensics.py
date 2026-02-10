
import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Set env vars BEFORE any application imports to satisfy Pydantic
os.environ["SECRET_KEY"] = "dummy"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost/db"
os.environ["SHOPIFY_API_KEY"] = "dummy"
os.environ["SHOPIFY_API_SECRET"] = "dummy"
os.environ["ANTHROPIC_API_KEY"] = "dummy"

# Now we can import app modules
from app.agents.execution import ExecutionAgent
from app.models import AuditLog

@pytest.mark.asyncio
async def test_forensic_identity_injection(db_session):
    """
    Verifies that Agent actions now carry Forensic Identity (client_id).
    """
    # 1. Setup Mock Environment
    merchant_id = "test_merchant_forensics"
    proposal_id = "test_prop_123"
    
    # Mock dependencies to bypass complex logic
    with patch("app.agents.execution.async_session_maker") as mock_session_maker:
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        
        # Mock Identity Service return
        mock_identity = MagicMock()
        mock_identity.client_id = "agent_execution_FORENSIC_123"
        mock_identity.agent_type = "execution"
        
        with patch("app.services.identity.IdentityService.get_or_create_agent_identity", return_value=mock_identity):
            
            # Setup DB Mock Returns
            mock_proposal = MagicMock()
            mock_proposal.status = "approved"
            mock_proposal.proposal_data = {"product_id": "p1"}
            mock_proposal.origin_execution_id = "orig_1"
            
            mock_session.execute.return_value.scalar_one_or_none.return_value = mock_proposal
            
            # 2. Run Agent
            agent = ExecutionAgent(merchant_id)
            
            # We intercept the _log_action call
            with patch("app.services.inbox.InboxService._log_action", new_callable=AsyncMock) as mock_log:
                try:
                    # Force a path that triggers logging (success mock)
                    with patch.object(agent, "_execute_klaviyo", return_value={'success': True}):
                        with patch.object(agent, "_execute_twilio", return_value={'success': True}): 
                            with patch.object(agent, "_simulate_execution", return_value={}):
                                with patch.object(agent, "_requires_async_auth", return_value=False):
                                    with patch("app.services.safety.SafetyService.is_paused", return_value=False):
                                         await agent.execute_campaign(proposal_id)
                except Exception as e:
                    # If we hit an error not caught above, print it
                    print(f"Agent Execution Error: {e}")
                    pass
                
                # 3. VERIFY
                call_args = mock_log.call_args
                if not call_args:
                    pytest.fail("InboxService._log_action was NOT called.")
                
                kwargs = call_args.kwargs
                actor = kwargs.get('actor')
                
                assert actor is not None, "Actor identity was NOT passed to log!"
                assert actor.client_id == "agent_execution_FORENSIC_123", "Wrong Client ID passed. Forensic Identity Injection FAILED."
                assert actor.agent_type == "execution", "Wrong Agent Type passed"
