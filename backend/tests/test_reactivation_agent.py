# backend/tests/test_reactivation_agent.py
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.reactivation import ReactivationAgent
from app.models import Customer, CommercialJourney, TouchLog

@pytest.fixture
def agent():
    return ReactivationAgent(merchant_id="test-merchant")

@pytest.mark.asyncio
@patch("app.agents.reactivation.LLMRouter")
async def test_reason_about_reactivation_push(mock_router_class, agent):
    # Mock LLM to approve reactivation
    mock_router = AsyncMock()
    mock_router.complete.return_value = {
        "content": json.dumps({
            "approved": True,
            "reason": "High-value customer hasn't purchased in 35 days, which is twice their normal cycle.",
            "churn_probability": 0.8
        })
    }
    agent.router = mock_router
    
    customer = MagicMock(spec=Customer)
    customer.first_name = "John"
    customer.rfm_segment = "champions"
    customer.last_order_date = datetime.utcnow() - timedelta(days=35)
    
    result = await agent._reason_about_reactivation(customer)
    
    assert result["approved"] is True
    assert "High-value" in result["reason"]
    assert result["churn_probability"] == 0.8

@pytest.mark.asyncio
@patch("app.agents.reactivation.LLMRouter")
async def test_reason_about_next_touch_pivot(mock_router_class, agent):
    # Mock LLM to pivot to SMS after email failed
    mock_router = AsyncMock()
    mock_router.complete.return_value = {
        "content": json.dumps({
            "channel": "sms",
            "tone": "urgent",
            "body": "Hey John, we missed you! Here is a special 20% off code.",
            "rationale": "Email was ignored, shifting to SMS for urgency.",
            "terminate": False
        })
    }
    agent.router = mock_router
    
    customer = MagicMock(spec=Customer)
    customer.first_name = "John"
    customer.sms_optin = True
    
    journey = MagicMock(spec=CommercialJourney)
    journey.id = 1
    journey.current_touch = 2
    
    history = [
        MagicMock(spec=TouchLog, channel='email', status='failed')
    ]
    
    result = await agent._reason_about_next_touch(customer, journey, history)
    
    assert result["channel"] == "sms"
    assert result["tone"] == "urgent"
    assert "SMS" in result["rationale"]

@pytest.mark.asyncio
@patch("app.agents.reactivation.ThoughtLogger.log_thought", new_callable=AsyncMock)
async def test_execute_touch_logging(mock_log_thought, agent):
    # Verify that execution logs a thought
    customer = MagicMock(spec=Customer)
    customer.first_name = "John"
    
    journey = MagicMock(spec=CommercialJourney)
    journey.current_touch = 1
    
    plan = {
        "channel": "email",
        "tone": "warm",
        "subject": "Hi!",
        "body": "Test message",
        "rationale": "Test",
        "terminate": False
    }
    
    mock_session = AsyncMock()
    
    # Mock credentials/connectors to avoid real calls
    with patch("app.integrations.credentials.get_credential_provider") as mock_get_provider, \
         patch("app.integrations.klaviyo.KlaviyoConnector.send_transactional", new_callable=AsyncMock) as mock_send:
        
        mock_provider = MagicMock()
        mock_provider.get_credentials = AsyncMock(return_value={"api_key": "test"})
        mock_get_provider.return_value = mock_provider
        mock_send.return_value = True
        
        await agent._execute_touch(journey, customer, plan, mock_session)
    
    assert mock_log_thought.called
    assert journey.current_touch == 2
