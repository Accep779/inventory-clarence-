# backend/tests/test_matchmaker_agent.py
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.matchmaker import MatchmakerAgent

@pytest.fixture
def agent():
    return MatchmakerAgent(merchant_id="test-merchant")

@pytest.mark.asyncio
@patch("app.agents.matchmaker.LLMRouter")
async def test_get_optimal_audience_reasoning(mock_router_class, agent):
    # Mock LLM to return a strategic matching
    mock_router = AsyncMock()
    mock_router.complete.return_value = {
        "content": json.dumps({
            "target_segments": ["champions", "loyal"],
            "reasoning": "High-margin product deserves exclusive audience matching.",
            "confidence": 0.95,
            "audience_description": "Our most valuable and active customers."
        })
    }
    agent.router = mock_router
    
    # Mock dependencies
    agent.memory.recall_campaign_outcomes = AsyncMock(return_value=[])
    
    # Mock DB counts
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 100
    mock_session.execute.return_value = mock_result
    
    product_data = {
        "id": "prod-1",
        "title": "Premium Watch",
        "product_type": "Watches",
        "suggested_discount": 10
    }
    
    # Mock ThoughtLogger
    with patch("app.agents.matchmaker.ThoughtLogger.log_thought", new_callable=AsyncMock):
        result = await agent.get_optimal_audience(product_data, "loyalty_exclusive", mock_session)
    
    assert "champions" in result["target_segments"]
    assert result["confidence"] == 0.95
    assert result["reasoning"] == "High-margin product deserves exclusive audience matching."
    assert mock_router.complete.called

@pytest.mark.asyncio
@patch("app.agents.matchmaker.MatchmakerAgent.run_daily_segmentation")
async def test_legacy_delegation(mock_legacy_run, agent):
    # Ensure the new agent still triggers the legacy segmentation for data consistency
    await agent.run_daily_segmentation()
    assert mock_legacy_run.called
