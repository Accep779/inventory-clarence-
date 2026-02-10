
import pytest
import requests
import httpx
from unittest.mock import MagicMock, AsyncMock, patch
from app.integrations.klaviyo import KlaviyoConnector
from app.integrations.twilio import TwilioConnector

# ============================================================================
# KLAVIYO TESTS (Sync requests via Executor)
# ============================================================================

@pytest.mark.asyncio
async def test_klaviyo_rate_limit_retry():
    """Verify Klaviyo connector retries on 429."""
    connector = KlaviyoConnector(api_key="pk_test_123")
    
    # Mock response to fail twice with 429, then succeed
    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 429
    mock_response_fail.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response_fail)
    
    mock_response_success = MagicMock()
    mock_response_success.status_code = 202
    mock_response_success.json.return_value = {"data": {"id": "123"}}
    
    with patch("requests.post") as mock_post:
        mock_post.side_effect = [
            requests.exceptions.HTTPError(response=mock_response_fail), # Attempt 1
            requests.exceptions.HTTPError(response=mock_response_fail), # Attempt 2
            mock_response_success # Attempt 3
        ]
        
        result = await connector.create_campaign("Test", "Subject", "Body", ["list_1"])
        
        assert result["status"] == "created"
        assert mock_post.call_count == 3

@pytest.mark.asyncio
async def test_klaviyo_server_error_retry():
    """Verify Klaviyo connector retries on 500."""
    connector = KlaviyoConnector(api_key="pk_test_123")
    
    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 503
    
    mock_response_success = MagicMock()
    mock_response_success.status_code = 202
    mock_response_success.json.return_value = {"data": {"id": "123"}}
    
    with patch("requests.post") as mock_post:
        mock_post.side_effect = [
            requests.exceptions.HTTPError(response=mock_response_fail),
            mock_response_success
        ]
        
        result = await connector.create_campaign("Test", "Subject", "Body", ["list_1"])
        
        assert result["status"] == "created"
        assert mock_post.call_count == 2

@pytest.mark.asyncio
async def test_klaviyo_client_error_no_retry():
    """Verify Klaviyo connector does NOTE retry on 400."""
    connector = KlaviyoConnector(api_key="pk_test_123")
    
    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 400
    mock_response_fail.text = "Bad Request"
    
    with patch("requests.post") as mock_post:
        # Should start failing immediately
        mock_post.side_effect = requests.exceptions.HTTPError(response=mock_response_fail)
        
        with pytest.raises(requests.exceptions.HTTPError):
            await connector.create_campaign("Test", "Subject", "Body", ["list_1"])
        
        # Should only call once
        assert mock_post.call_count == 1


# ============================================================================
# TWILIO TESTS (Async httpx)
# ============================================================================

@pytest.mark.asyncio
async def test_twilio_rate_limit_retry():
    """Verify Twilio connector retries on 429."""
    connector = TwilioConnector(api_key="AC123:token")
    
    # httpx requires request object for raise_for_status context
    req = httpx.Request("POST", "https://api.twilio.com")
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # Setup responses
        err_response = httpx.Response(429, request=req)
        ok_response = httpx.Response(200, json={"sid": "SM123"}, request=req)
        
        # Attempt 1: 429 -> raise
        # Attempt 2: 200 -> ok
        mock_post.side_effect = [
            httpx.HTTPStatusError("Rate Limit", request=req, response=err_response),
            ok_response
        ]
        
        result = await connector.send_transactional("123", "Subject", "Body")
        
        assert result["status"] == "sent"
        assert mock_post.call_count == 2

@pytest.mark.asyncio
async def test_twilio_timeout_retry():
    """Verify Twilio connector retries on Timeout."""
    connector = TwilioConnector(api_key="AC123:token")
    
    req = httpx.Request("POST", "https://api.twilio.com")
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        ok_response = httpx.Response(200, json={"sid": "SM123"}, request=req)
        
        mock_post.side_effect = [
            httpx.TimeoutException("Timeout"),
            ok_response
        ]
        
        result = await connector.send_transactional("123", "Subject", "Body")
        
        assert result["status"] == "sent"
        assert mock_post.call_count == 2
