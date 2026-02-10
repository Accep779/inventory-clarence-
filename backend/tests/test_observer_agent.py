# backend/tests/test_observer_agent.py
"""
Unit Tests for Observer Agent Intelligence
==========================================

Verifies the "Brain + Math" combination:
1. Deterministic velocity calculations
2. AI-driven latent risk detection
3. Combined final classification
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.observer import ObserverAgent

class TestObserverAgent:
    
    @pytest.fixture
    def agent(self):
        return ObserverAgent(merchant_id="test-merchant")

    def test_base_metrics_calculation(self, agent):
        """Verify deterministic math is correct."""
        product_data = {
            "variants": [{"price": "100.00", "inventory_quantity": 10}],
            "days_since_last_sale": 10,
            "units_sold_30d": 5
        }
        
        metrics = agent._calculate_base_metrics(product_data)
        
        assert metrics["price"] == 100.0
        assert metrics["inventory"] == 10
        assert metrics["stuck_value"] == 1000.0
        # Turnover: (5/10) * 12 = 6.0
        assert metrics["turnover_rate"] == 6.0
        assert metrics["days_since_last_sale"] == 10

    @pytest.mark.asyncio
    @patch("app.agents.observer.LLMRouter")
    async def test_observe_product_with_ai_bonus(self, mock_router_class, agent):
        """Verify AI bonus increases severity correctly."""
        
        # Mock LLM to return a 'severity_bonus' of 1
        mock_router = AsyncMock()
        mock_router.complete.return_value = {
            "content": json.dumps({
                "latent_risk": True,
                "severity_bonus": 1,
                "summary": "Velocity is dropping faster than seasonal norms.",
                "recommendation": "act"
            })
        }
        agent.router = mock_router
        
        # Mock Memory Recall
        agent.memory.recall_thoughts = AsyncMock(return_value=[])
        
        # Product just below 'low' threshold (e.g. score 67)
        product_data = {
            "id": "prod-1",
            "title": "Test Product",
            "variants": [{"price": "100.00", "inventory_quantity": 10}],
            "days_since_last_sale": 5,
            "units_sold_30d": 10 
        }
        
        # Mock ThoughtLogger
        with patch("app.agents.observer.ThoughtLogger.log_thought", new_callable=AsyncMock):
            result = await agent.observe_product(product_data, MagicMock())
        
        # If score > 65, base_severity = "none"
        # none + 1 bonus = "low"
        assert result["severity"] == "low"
        assert result["is_latent"] is True
        assert result["reasoning"] == "Velocity is dropping faster than seasonal norms."

    def test_finalize_classification_clamping(self, agent):
        """Verify severity doesn't overflow 'critical'."""
        metrics = {"velocity_score": 10, "days_since_last_sale": 100} # base = critical
        reasoning = {"severity_bonus": 2}
        
        classification = agent._finalize_classification(metrics, reasoning)
        assert classification["severity"] == "critical"

if __name__ == "__main__":
    pytest.main([__file__])
