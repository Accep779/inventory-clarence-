# backend/tests/test_resilience.py
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.safety import SafetyService
from app.services.llm_router import LLMRouter, LLMRouterError
from app.agents.execution import ExecutionAgent

@pytest.mark.asyncio
async def test_global_kill_switch():
    """Verify that global pause stops execution."""
    with patch("redis.Redis.from_url") as mock_redis_factory:
        mock_redis = MagicMock()
        mock_redis_factory.return_value = mock_redis
        mock_redis.get.return_value = b"true"
        
        with patch("app.agents.execution.async_session_maker") as mock_session_maker:
            mock_session = AsyncMock()
            mock_session_maker.return_value.__aenter__.return_value = mock_session
            
            # Mock _mark_campaign_failed to avoid DB issues
            with patch.object(ExecutionAgent, "_mark_campaign_failed", new_callable=AsyncMock) as mock_fail:
                agent = ExecutionAgent(merchant_id="test_merchant")
                result = await agent.execute_campaign(proposal_id="test_proposal")
                
                assert result['status'] == 'blocked'
                assert result['reason'] == 'safety_pause'
                mock_fail.assert_called_once()

@pytest.mark.asyncio
async def test_llm_budget_lock():
    """Verify that exceeding budget raises LLMRouterError."""
    router = LLMRouter()
    
    with patch("app.services.llm_router.async_session_maker") as mock_session_maker:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (50.0, 51.0)
        mock_session.execute.return_value = mock_result
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        
        with pytest.raises(LLMRouterError):
            await router.complete(
                task_type="strategy_generation",
                system_prompt="test",
                user_prompt="test",
                merchant_id="test_merchant"
            )

@pytest.mark.asyncio
async def test_idempotency_key_generation():
    """Verify that ExecutionAgent generates deterministic keys."""
    agent = ExecutionAgent(merchant_id="test_merchant")
    proposal_id = "prop_123"
    
    with patch.object(ExecutionAgent, "_execute_klaviyo", new_callable=AsyncMock, return_value=True) as mock_klaviyo:
        with patch.object(ExecutionAgent, "_execute_twilio", new_callable=AsyncMock, return_value=True) as mock_twilio:
            with patch("app.agents.execution.async_session_maker") as mock_session_maker:
                mock_session = AsyncMock()
                mock_session_maker.return_value.__aenter__.return_value = mock_session
                
                # Mock Return values for DB calls
                mock_proposal = MagicMock()
                mock_proposal.status = "approved"
                mock_proposal.proposal_data = {"product_id": "p1", "copy": {}, "audience": {}}
                mock_proposal.origin_execution_id = "orig_1"
                
                mock_product = MagicMock()
                mock_product.id = "p1"
                mock_product.total_inventory = 100
                
                mock_merchant = MagicMock()
                
                # Mock results
                m1, m2, m3, m4 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
                m1.scalar_one_or_none.return_value = mock_proposal
                m2.scalar_one_or_none.return_value = mock_product
                m3.scalar_one.return_value = mock_merchant
                m4.scalar_one_or_none.return_value = MagicMock(id="log_1")
                
                # Side effect for sequential DB calls (provide extras to avoid StopIteration)
                mock_session.execute.side_effect = [m1, m2, m3, m4, m1, m1, m1, m1, m1, m1]
                
                with patch.object(ExecutionAgent, "_simulate_execution", return_value={"blocked": False}):
                    with patch.object(ExecutionAgent, "_requires_async_auth", return_value=False):
                        with patch("app.services.safety.SafetyService.is_paused", return_value=False):
                            with patch("app.services.shadow_inventory.ShadowInventory.get_available_quantity", return_value=50):
                                await agent.execute_campaign(proposal_id)
                                
                                mock_klaviyo.assert_called()
                                # Check the 7th positional argument (index 6)
                                assert mock_klaviyo.call_args.args[6] == f"{proposal_id}:0"
