import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.agents.execution import ExecutionAgent, RetryableError, RateLimitError

@pytest.mark.asyncio
async def test_simulate_execution():
    agent = ExecutionAgent("test_merchant")
    
    with patch('app.services.llm_router.LLMRouter.complete', new_callable=AsyncMock) as mock_complete:
        mock_complete.return_value = {
            'content': '{"blocked": false, "stagger_required": true, "batch_size": 10, "stagger_delay_seconds": 2, "rationale": "Test rationale"}'
        }
        
        simulation = await agent._simulate_execution("test_proposal")
        
        assert simulation['blocked'] is False
        assert simulation['stagger_required'] is True
        assert simulation['batch_size'] == 10
        assert simulation['stagger_delay_seconds'] == 2

@pytest.mark.asyncio
async def test_execute_campaign_blocked():
    agent = ExecutionAgent("test_merchant")
    
    with patch.object(agent, '_simulate_execution', new_callable=AsyncMock) as mock_sim:
        mock_sim.return_value = {'blocked': True, 'reason': 'Testing blockage'}
        with patch.object(agent, '_mark_campaign_failed', new_callable=AsyncMock) as mock_fail:
            result = await agent.execute_campaign("test_proposal")
            
            assert result['status'] == 'blocked'
            mock_fail.assert_called_once()

@pytest.mark.asyncio
async def test_adaptive_throttling_in_twilio():
    agent = ExecutionAgent("test_merchant")
    merchant = MagicMock()
    campaign = MagicMock()
    campaign.target_segments = ['test_segment']
    copy = {'sms_body': 'hello'}
    simulation = {'batch_size': 50, 'stagger_delay_seconds': 1}
    
    # Mock database and integrations
    with patch('app.agents.execution.async_session_maker') as mock_session_maker, \
         patch('app.agents.execution.get_credential_provider') as mock_provider, \
         patch('app.integrations.twilio.TwilioConnector', spec=True), \
         patch('app.services.waterfall.WaterfallService') as mock_waterfall:
             
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        
        # Mock credentials
        mock_prov_instance = AsyncMock()
        mock_prov_instance.get_credentials.return_value = {'sid': 'sid', 'token': 'token'}
        mock_provider.return_value = mock_prov_instance
        
        # Mock customer query
        mock_customer = MagicMock()
        mock_customer.phone = '+1234567890'
        mock_res = MagicMock()
        mock_res.scalars.return_value.all.return_value = [mock_customer]
        mock_session.execute.return_value = mock_res
        
        success = await agent._execute_twilio(merchant, campaign, copy, "Product", mock_session, simulation)
        
        assert success is True
        # Verify adaptive parameters used in Waterfall
        mock_waterfall.assert_called_once_with(batch_size=50, delay_seconds=1)
