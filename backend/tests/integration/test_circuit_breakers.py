import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta

from app.integrations.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    get_klaviyo_circuit_breaker,
    get_twilio_circuit_breaker
)
from app.config import get_settings

settings = get_settings()

class StatefulRedisMock:
    """A slightly more intelligent Redis mock that maintains state between calls."""
    def __init__(self):
        self.data = {}
        self.expires = {}

    def get(self, key):
        if key in self.expires and datetime.utcnow() > self.expires[key]:
            del self.data[key]
            del self.expires[key]
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = str(value)
        return True

    def incr(self, key):
        val = int(self.data.get(key, 0)) + 1
        self.data[key] = str(val)
        return val

    def delete(self, *keys):
        count = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                count += 1
        return count

    def expire(self, key, seconds):
        self.expires[key] = datetime.utcnow() + timedelta(seconds=seconds)
        return True

@pytest.fixture
def stateful_redis():
    return StatefulRedisMock()

@pytest.fixture(autouse=True)
def mock_get_redis(stateful_redis):
    with patch("app.integrations.circuit_breaker.get_redis_client", return_value=stateful_redis):
        yield stateful_redis

@pytest.fixture
def mock_db():
    db = AsyncMock()
    # Mock commit to be a no-op
    db.commit = AsyncMock()
    return db

@pytest.mark.asyncio
async def test_1_normal_operation_closed(stateful_redis):
    """Test 1: Normal Operation (CLOSED state) - 100 successful requests."""
    breaker = CircuitBreaker("klaviyo", failure_threshold=5)
    
    async def success_func():
        return {"status": "success"}

    for _ in range(100):
        result = await breaker.call(success_func)
        assert result["status"] == "success"

    assert breaker._get_state() == CircuitState.CLOSED
    assert stateful_redis.get(breaker.key_failures) is None

@pytest.mark.asyncio
async def test_2_failure_detection_opens(stateful_redis, mock_db):
    """Test 2: Failure Detection (CLOSED → OPEN) - Opens after 5 failures."""
    breaker = CircuitBreaker("klaviyo", failure_threshold=5, timeout_seconds=60)
    
    async def failing_func():
        raise Exception("500 Internal Server Error")

    # Simulate 5 failures
    for i in range(5):
        try:
            # Pass merchant_id and db to test alert logic
            await breaker.call(failing_func, merchant_id="m_123", db=mock_db)
        except Exception as e:
            if i < 4:
                assert "500" in str(e)
            else:
                pass # The 5th failure might raise the original or the OpenError depending on implementation
                # actually _record_failure is called after the exception is raised.
                # So the 5th call raises the original exception, but transitions state to OPEN.

    assert breaker._get_state() == CircuitState.OPEN

    # 6th call should fail immediately with CircuitBreakerOpenError
    start_time = time.time()
    with pytest.raises(CircuitBreakerOpenError) as excinfo:
        await breaker.call(failing_func)
    
    elapsed = time.time() - start_time
    assert elapsed < 0.1
    assert "OPEN" in str(excinfo.value)
    
    # Verify InboxItem creation was attempted
    assert mock_db.commit.call_count >= 1

@pytest.mark.asyncio
async def test_3_timeout_and_half_open(stateful_redis):
    """Test 3: Timeout Period (OPEN persistence) and transition to HALF_OPEN."""
    timeout = 2  # Short timeout for testing
    breaker = CircuitBreaker("klaviyo", failure_threshold=1, timeout_seconds=timeout)
    
    async def failing_func():
        raise Exception("500 Error")

    # Open it
    with pytest.raises(Exception):
        await breaker.call(failing_func)
    
    assert breaker._get_state() == CircuitState.OPEN
    
    # Try immediately - should fail
    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(failing_func)
    
    # Wait for timeout
    await asyncio.sleep(timeout + 0.1)
    
    # Next call should attempt transition to HALF_OPEN
    async def success_func():
        return "ok"
        
    # The call SHOULD transition it to HALF_OPEN and then CLOSED immediately because it succeeds
    # Let's check state after it transitions to half-open but before it finishes maybe?
    # Hard to do with current implementation. Let's just verify it succeeds.
    result = await breaker.call(success_func)
    assert result == "ok"
    assert breaker._get_state() == CircuitState.CLOSED

@pytest.mark.asyncio
async def test_4_recovery_half_open_to_closed(stateful_redis):
    """Test 4: Recovery Testing (HALF_OPEN → CLOSED)"""
    breaker = CircuitBreaker("klaviyo", failure_threshold=1, timeout_seconds=1)
    
    # Manually put in HALF_OPEN
    stateful_redis.set(breaker.key_state, CircuitState.HALF_OPEN.value)
    
    async def success_func():
        return "success"
        
    result = await breaker.call(success_func)
    assert result == "success"
    assert breaker._get_state() == CircuitState.CLOSED
    assert stateful_redis.get(breaker.key_timeout_multiplier) is None

@pytest.mark.asyncio
async def test_5_failed_recovery_exponential_backoff(stateful_redis):
    """Test 5: Failed Recovery (HALF_OPEN → OPEN) with Exponential Backoff."""
    breaker = CircuitBreaker("klaviyo", failure_threshold=1, timeout_seconds=60)
    
    # Cycle 1: Open it
    async def failing_func():
        raise Exception("500 Error")
        
    with pytest.raises(Exception):
        await breaker.call(failing_func)
    
    assert breaker._get_state() == CircuitState.OPEN
    assert int(stateful_redis.get(breaker.key_timeout_multiplier)) == 1
    
    # Manually set last failure to far back but keep multiplier
    stateful_redis.set(breaker.key_last_failure, (datetime.utcnow() - timedelta(seconds=61)).isoformat())
    
    # Next call will transition to HALF_OPEN and fail
    with pytest.raises(Exception):
        await breaker.call(failing_func)
        
    assert breaker._get_state() == CircuitState.OPEN
    # Multiplier should have increased
    assert int(stateful_redis.get(breaker.key_timeout_multiplier)) == 2
    
    # Next timeout should be 120s
    stateful_redis.set(breaker.key_last_failure, (datetime.utcnow() - timedelta(seconds=65)).isoformat())
    # Should still be OPEN because timeout is now 120
    with pytest.raises(CircuitBreakerOpenError) as excinfo:
        await breaker.call(failing_func)
    assert excinfo.value.retry_after > 50

@pytest.mark.asyncio
async def test_6_manual_reset(stateful_redis):
    """Test 6: Manual Circuit Control."""
    breaker = CircuitBreaker("klaviyo", failure_threshold=1)
    
    # Open it
    stateful_redis.set(breaker.key_state, CircuitState.OPEN.value)
    
    # Reset it
    breaker.reset()
    
    assert breaker._get_state() == CircuitState.CLOSED
    assert stateful_redis.get(breaker.key_state) is None

@pytest.mark.asyncio
async def test_7_service_isolation(stateful_redis):
    """Test 7: Per-Service Isolation."""
    klaviyo = get_klaviyo_circuit_breaker()
    twilio = get_twilio_circuit_breaker()
    
    async def failing_func():
        raise Exception("500 Error")
        
    # Open klaviyo
    for _ in range(5):
        try:
            await klaviyo.call(failing_func)
        except:
            pass
            
    assert klaviyo._get_state() == CircuitState.OPEN
    assert twilio._get_state() == CircuitState.CLOSED
    
    # Twilio should still work
    async def success_func():
        return "sms_sent"
        
    result = await twilio.call(success_func)
    assert result == "sms_sent"
