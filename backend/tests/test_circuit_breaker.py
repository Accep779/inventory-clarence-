# backend/tests/test_circuit_breaker.py
"""
Tests for Circuit Breaker Pattern.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from app.integrations.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError
)


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.get.return_value = None
    redis.incr.return_value = 1
    return redis


@pytest.fixture
def circuit_breaker(mock_redis):
    """Create a circuit breaker with mocked Redis."""
    with patch('app.integrations.circuit_breaker.get_redis_client', return_value=mock_redis):
        return CircuitBreaker(
            service_name="test_service",
            failure_threshold=3,
            timeout_seconds=60
        )


@pytest.mark.asyncio
async def test_circuit_starts_closed(circuit_breaker, mock_redis):
    """Circuit should start in CLOSED state."""
    mock_redis.get.return_value = None
    
    state = circuit_breaker._get_state()
    assert state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_circuit_opens_after_threshold_failures(circuit_breaker, mock_redis):
    """Circuit should open after configured number of failures."""
    # Simulate failures reaching threshold
    mock_redis.incr.return_value = 3  # Threshold is 3
    
    class ServerError(Exception):
        def __init__(self):
            self.status_code = 500
    
    circuit_breaker._record_failure(ServerError())
    
    # Verify circuit opened
    mock_redis.set.assert_any_call(
        "circuit_breaker:test_service:state",
        CircuitState.OPEN.value
    )


@pytest.mark.asyncio
async def test_open_circuit_rejects_calls(circuit_breaker, mock_redis):
    """Open circuit should reject calls immediately."""
    mock_redis.get.side_effect = lambda key: {
        "circuit_breaker:test_service:state": CircuitState.OPEN.value,
        "circuit_breaker:test_service:last_failure": datetime.utcnow().isoformat()
    }.get(key)
    
    async def dummy_func():
        return "success"
    
    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        await circuit_breaker.call(dummy_func)
    
    assert "test_service" in str(exc_info.value)
    assert "OPEN" in str(exc_info.value)


@pytest.mark.asyncio
async def test_circuit_resets_on_success(circuit_breaker, mock_redis):
    """Successful call should reset failure count."""
    mock_redis.get.return_value = None  # CLOSED state
    
    async def successful_func():
        return "success"
    
    result = await circuit_breaker.call(successful_func)
    
    assert result == "success"
    mock_redis.delete.assert_called()  # Should reset failure tracking


@pytest.mark.asyncio
async def test_half_open_allows_test_calls(circuit_breaker, mock_redis):
    """Half-open circuit should allow limited test calls."""
    mock_redis.get.side_effect = lambda key: {
        "circuit_breaker:test_service:state": CircuitState.HALF_OPEN.value,
        "circuit_breaker:test_service:half_open_calls": "1"
    }.get(key)
    
    async def test_func():
        return "recovered"
    
    result = await circuit_breaker.call(test_func)
    assert result == "recovered"


@pytest.mark.asyncio
async def test_get_status_returns_info(circuit_breaker, mock_redis):
    """get_status should return circuit breaker info."""
    mock_redis.get.side_effect = lambda key: {
        "circuit_breaker:test_service:state": CircuitState.CLOSED.value,
        "circuit_breaker:test_service:failures": "2",
        "circuit_breaker:test_service:last_failure": None
    }.get(key)
    
    status = circuit_breaker.get_status()
    
    assert status["service"] == "test_service"
    assert status["state"] == CircuitState.CLOSED.value
    assert status["failure_threshold"] == 3


@pytest.mark.asyncio
async def test_reset_clears_state(circuit_breaker, mock_redis):
    """reset() should clear all circuit breaker state."""
    circuit_breaker.reset()
    
    # Verify all keys deleted
    assert mock_redis.delete.call_count >= 4


@pytest.mark.asyncio
async def test_client_errors_dont_trigger_circuit(circuit_breaker, mock_redis):
    """4xx errors should not count toward circuit breaker."""
    class ClientError(Exception):
        def __init__(self):
            self.status_code = 400
    
    initial_incr_count = mock_redis.incr.call_count
    circuit_breaker._record_failure(ClientError())
    
    # Should not have incremented
    assert mock_redis.incr.call_count == initial_incr_count
