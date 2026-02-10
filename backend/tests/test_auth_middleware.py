"""
Tests for JWT Authentication Middleware.

Verifies token creation, validation, and error handling.
"""

import pytest
from datetime import timedelta
from unittest.mock import patch

from fastapi import HTTPException
from jose import jwt

# Constants matching the middleware
ALGORITHM = "HS256"
TEST_SECRET = "test-secret-key-for-testing-only"


@pytest.fixture
def mock_secret():
    """Mock the secret key for all tests."""
    with patch('app.auth_middleware._get_secret_key', return_value=TEST_SECRET):
        yield TEST_SECRET


class TestCreateAccessToken:
    """Tests for create_access_token function."""
    
    def test_creates_valid_token(self, mock_secret):
        """Token should be decodable and contain merchant_id."""
        from app.auth_middleware import create_access_token
        
        merchant_id = "test-merchant-123"
        token = create_access_token(merchant_id)
        
        payload = jwt.decode(token, TEST_SECRET, algorithms=[ALGORITHM])
        
        assert payload["sub"] == merchant_id
        assert "exp" in payload
    
    def test_custom_expiration(self, mock_secret):
        """Token should respect custom expiration delta."""
        from app.auth_middleware import create_access_token
        
        merchant_id = "test-merchant-456"
        short_expiry = timedelta(minutes=5)
        token = create_access_token(merchant_id, expires_delta=short_expiry)
        
        payload = jwt.decode(token, TEST_SECRET, algorithms=[ALGORITHM])
        
        assert payload["sub"] == merchant_id


class TestGetCurrentTenant:
    """Tests for get_current_tenant dependency."""
    
    @pytest.mark.asyncio
    async def test_valid_token_returns_merchant_id(self, mock_secret):
        """Valid Bearer token should return the merchant_id."""
        from app.auth_middleware import create_access_token, get_current_tenant
        
        merchant_id = "valid-merchant-789"
        token = create_access_token(merchant_id)
        authorization = f"Bearer {token}"
        
        result = await get_current_tenant(authorization)
        
        assert result == merchant_id
    
    @pytest.mark.asyncio
    async def test_missing_bearer_prefix_raises_401(self, mock_secret):
        """Token without 'Bearer ' prefix should raise 401."""
        from app.auth_middleware import create_access_token, get_current_tenant
        
        token = create_access_token("some-merchant")
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant(token)  # No "Bearer " prefix
        
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self, mock_secret):
        """Invalid/tampered token should raise 401."""
        from app.auth_middleware import get_current_tenant
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant("Bearer invalid.token.here")
        
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_token_with_wrong_secret_raises_401(self, mock_secret):
        """Token signed with different secret should raise 401."""
        from app.auth_middleware import get_current_tenant
        
        # Create token with a different secret
        wrong_secret = "wrong-secret-key"
        payload = {"sub": "merchant-abc"}
        token = jwt.encode(payload, wrong_secret, algorithm=ALGORITHM)
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant(f"Bearer {token}")
        
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_token_without_sub_raises_401(self, mock_secret):
        """Token without 'sub' claim should raise 401."""
        from app.auth_middleware import get_current_tenant
        
        payload = {"other": "data"}  # No 'sub' claim
        token = jwt.encode(payload, TEST_SECRET, algorithm=ALGORITHM)
        
        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant(f"Bearer {token}")
        
        assert exc_info.value.status_code == 401
