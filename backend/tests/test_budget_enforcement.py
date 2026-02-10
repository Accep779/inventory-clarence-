# backend/tests/test_budget_enforcement.py
"""
Tests for Budget Enforcement Service.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.budget_enforcement import (
    BudgetEnforcementService,
    BudgetExceededError,
    estimate_llm_cost,
    estimate_prompt_cost
)


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_merchant():
    """Create a mock Merchant."""
    merchant = MagicMock()
    merchant.id = "test-merchant-id"
    merchant.plan = "trial"
    merchant.monthly_llm_budget = Decimal("50.00")
    merchant.current_llm_spend = Decimal("0.00")
    merchant.budget_reset_date = datetime.utcnow()
    return merchant


@pytest.mark.asyncio
async def test_check_budget_allows_under_limit(mock_session, mock_merchant):
    """Budget check should allow operations under limit."""
    mock_session.get.return_value = mock_merchant
    
    # Mock usage query to return low usage
    mock_result = MagicMock()
    mock_result.scalar.return_value = Decimal("10.00")
    mock_session.execute.return_value = mock_result
    
    service = BudgetEnforcementService(mock_session)
    
    allowed, reason = await service.check_budget(
        merchant_id="test-merchant-id",
        estimated_cost=Decimal("5.00")
    )
    
    assert allowed is True
    assert reason is None


@pytest.mark.asyncio
async def test_check_budget_blocks_over_limit(mock_session, mock_merchant):
    """Budget check should block operations that would exceed limit."""
    mock_session.get.return_value = mock_merchant
    
    # Mock usage query to return high usage
    mock_result = MagicMock()
    mock_result.scalar.return_value = Decimal("48.00")  # Already at 48/50
    mock_session.execute.return_value = mock_result
    
    service = BudgetEnforcementService(mock_session)
    
    allowed, reason = await service.check_budget(
        merchant_id="test-merchant-id",
        estimated_cost=Decimal("5.00")  # Would push to 53/50
    )
    
    assert allowed is False
    assert "exceeded" in reason.lower()


@pytest.mark.asyncio
async def test_check_and_raise_throws_error(mock_session, mock_merchant):
    """check_and_raise should throw BudgetExceededError when over limit."""
    mock_session.get.return_value = mock_merchant
    
    # Mock high usage
    mock_result = MagicMock()
    mock_result.scalar.return_value = Decimal("50.00")
    mock_session.execute.return_value = mock_result
    
    service = BudgetEnforcementService(mock_session)
    
    with pytest.raises(BudgetExceededError) as exc_info:
        await service.check_and_raise(
            merchant_id="test-merchant-id",
            estimated_cost=Decimal("1.00")
        )
    
    assert exc_info.value.limit == Decimal("50.00")


@pytest.mark.asyncio
async def test_soft_limit_warning_sent(mock_session, mock_merchant):
    """Crossing 80% threshold should trigger warning."""
    mock_session.get.return_value = mock_merchant
    
    # First query: Usage at 38 (under 80%)
    # After operation: 42 (over 80% but under 100%)
    mock_result = MagicMock()
    mock_result.scalar.return_value = Decimal("38.00")
    
    # No recent warning exists
    mock_warning_result = MagicMock()
    mock_warning_result.scalar_one_or_none.return_value = None
    
    mock_session.execute.side_effect = [mock_result, mock_warning_result]
    
    service = BudgetEnforcementService(mock_session)
    
    allowed, reason = await service.check_budget(
        merchant_id="test-merchant-id",
        estimated_cost=Decimal("5.00")  # Would push to 43/50 = 86%
    )
    
    assert allowed is True
    # Warning should have been added to session
    mock_session.add.assert_called_once()


def test_estimate_llm_cost_claude():
    """Estimate cost for Claude model."""
    cost = estimate_llm_cost(
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        input_tokens=1000,
        output_tokens=500
    )
    
    # Claude: $3/1M input, $15/1M output
    # 1000 * 0.000003 + 500 * 0.000015 = 0.003 + 0.0075 = 0.0105
    assert cost == Decimal("0.0105")


def test_estimate_llm_cost_gpt4o_mini():
    """Estimate cost for GPT-4o-mini model."""
    cost = estimate_llm_cost(
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=1000,
        output_tokens=500
    )
    
    # GPT-4o-mini: $0.15/1M input, $0.6/1M output
    # 1000 * 0.00000015 + 500 * 0.0000006 = 0.00015 + 0.0003 = 0.00045
    assert cost == Decimal("0.00045")


def test_estimate_prompt_cost():
    """Estimate cost from prompt length."""
    # 4000 characters = ~1000 tokens input, ~500 tokens output
    cost = estimate_prompt_cost(
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        prompt_length=4000
    )
    
    assert cost > Decimal("0")
    assert cost < Decimal("1")  # Sanity check


@pytest.mark.asyncio
async def test_get_usage_summary(mock_session, mock_merchant):
    """get_usage_summary should return usage stats."""
    mock_session.get.return_value = mock_merchant
    
    mock_result = MagicMock()
    mock_result.scalar.return_value = Decimal("25.00")
    mock_session.execute.return_value = mock_result
    
    service = BudgetEnforcementService(mock_session)
    
    summary = await service.get_usage_summary("test-merchant-id")
    
    assert summary["current_usage"] == 25.00
    assert summary["budget_limit"] == 50.00
    assert summary["percentage_used"] == 50.0
    assert summary["remaining"] == 25.00


@pytest.mark.asyncio
async def test_plan_based_default_budgets(mock_session):
    """Different plans should have different default budgets."""
    service = BudgetEnforcementService(mock_session)
    
    trial_merchant = MagicMock()
    trial_merchant.plan = "trial"
    trial_merchant.monthly_llm_budget = None
    
    growth_merchant = MagicMock()
    growth_merchant.plan = "growth"
    growth_merchant.monthly_llm_budget = None
    
    assert service._get_budget_limit(trial_merchant) == Decimal("50.00")
    assert service._get_budget_limit(growth_merchant) == Decimal("500.00")
