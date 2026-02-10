# backend/tests/test_idempotency.py
"""
Tests for Idempotency Middleware.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.middleware.idempotency import IdempotencyMiddleware, IdempotencyError


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.get.return_value = None
    redis.setex.return_value = True
    redis.exists.return_value = 0
    redis.delete.return_value = 1
    return redis


@pytest.fixture
def idempotency_middleware(mock_redis):
    """Create middleware with mocked Redis."""
    with patch('app.middleware.idempotency.get_redis_client', return_value=mock_redis):
        return IdempotencyMiddleware()


@pytest.mark.asyncio
async def test_first_request_executes_handler(idempotency_middleware, mock_redis):
    """First request should execute handler and cache result."""
    mock_redis.get.return_value = None  # Not in cache
    
    async def handler():
        return {"status": "approved", "item_id": "test123"}
    
    result = await idempotency_middleware.ensure_idempotent(
        key="idempotency-key-1",
        merchant_id="merchant-1",
        endpoint="/inbox/test/approve",
        handler=handler
    )
    
    assert result["status"] == "approved"
    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_duplicate_request_returns_cached_result(idempotency_middleware, mock_redis):
    """Duplicate request should return cached result without executing handler."""
    import json
    
    cached_result = {"status": "approved", "item_id": "test123"}
    mock_redis.get.return_value = json.dumps(cached_result)
    
    handler_called = False
    async def handler():
        nonlocal handler_called
        handler_called = True
        return {"status": "should_not_be_returned"}
    
    result = await idempotency_middleware.ensure_idempotent(
        key="idempotency-key-1",
        merchant_id="merchant-1",
        endpoint="/inbox/test/approve",
        handler=handler
    )
    
    assert result == cached_result
    assert not handler_called  # Handler should NOT be called


@pytest.mark.asyncio
async def test_different_keys_execute_separately(idempotency_middleware, mock_redis):
    """Different keys should execute handlers independently."""
    mock_redis.get.return_value = None
    
    call_count = 0
    async def handler():
        nonlocal call_count
        call_count += 1
        return {"call": call_count}
    
    await idempotency_middleware.ensure_idempotent(
        key="key-1",
        merchant_id="merchant-1",
        endpoint="/inbox/test/approve",
        handler=handler
    )
    
    await idempotency_middleware.ensure_idempotent(
        key="key-2",
        merchant_id="merchant-1",
        endpoint="/inbox/test/approve",
        handler=handler
    )
    
    assert call_count == 2  # Both handlers should execute


@pytest.mark.asyncio
async def test_handler_error_not_cached(idempotency_middleware, mock_redis):
    """Errors should NOT be cached to allow retry."""
    mock_redis.get.return_value = None
    
    async def failing_handler():
        raise ValueError("Something went wrong")
    
    with pytest.raises(ValueError):
        await idempotency_middleware.ensure_idempotent(
            key="key-1",
            merchant_id="merchant-1",
            endpoint="/inbox/test/approve",
            handler=failing_handler
        )
    
    # setex should NOT be called for errors
    mock_redis.setex.assert_not_called()


def test_cache_key_includes_merchant_and_endpoint(idempotency_middleware):
    """Cache key should be unique per merchant AND endpoint."""
    key1 = idempotency_middleware._build_cache_key(
        key="same-key",
        merchant_id="merchant-1",
        endpoint="/inbox/1/approve"
    )
    
    key2 = idempotency_middleware._build_cache_key(
        key="same-key",
        merchant_id="merchant-2",  # Different merchant
        endpoint="/inbox/1/approve"
    )
    
    key3 = idempotency_middleware._build_cache_key(
        key="same-key",
        merchant_id="merchant-1",
        endpoint="/inbox/2/approve"  # Different endpoint
    )
    
    assert key1 != key2  # Different merchants
    assert key1 != key3  # Different endpoints


def test_check_key_exists(idempotency_middleware, mock_redis):
    """check_key_exists should query Redis correctly."""
    mock_redis.exists.return_value = 1
    
    exists = idempotency_middleware.check_key_exists(
        key="test-key",
        merchant_id="merchant-1",
        endpoint="/inbox/test/approve"
    )
    
    assert exists is True


def test_invalidate_key(idempotency_middleware, mock_redis):
    """invalidate_key should delete from Redis."""
    mock_redis.delete.return_value = 1
    
    result = idempotency_middleware.invalidate_key(
        key="test-key",
        merchant_id="merchant-1",
        endpoint="/inbox/test/approve"
    )
    
    assert result is True
    mock_redis.delete.assert_called_once()
