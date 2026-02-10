"""
JWT Authentication Middleware.

Provides secure tenant isolation by validating signed JWTs
that encode the merchant_id.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Header, HTTPException, Depends
from jose import JWTError, jwt


# JWT Configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


def _get_secret_key() -> str:
    """Lazy-load the secret key to support testing."""
    from app.config import get_settings
    return get_settings().SECRET_KEY


def create_access_token(merchant_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT for a merchant.
    
    Args:
        merchant_id: The merchant's UUID.
        expires_delta: Optional custom expiration time.
        
    Returns:
        A signed JWT string.
    """
    to_encode = {"sub": merchant_id}
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode["exp"] = expire
    
    encoded_jwt = jwt.encode(to_encode, _get_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt


def create_agent_token(agent_ctx: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT specifically for an Agent.
    Includes scopes and client_id in the payload.
    """
    to_encode = {
        "sub": agent_ctx["client_id"],
        "type": "agent",
        "agent_type": agent_ctx["agent_type"],
        "merchant_id": agent_ctx["merchant_id"],
        "scopes": agent_ctx.get("scopes", [])
    }
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode["exp"] = expire
    
    encoded_jwt = jwt.encode(to_encode, _get_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt


from fastapi import Header, HTTPException, Depends, Request

async def get_current_tenant(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> str:
    """
    FastAPI dependency that extracts and validates the merchant_id from a JWT.
    Supports both 'Authorization: Bearer' header and 'auth_token' cookie.
    
    Returns:
        The validated merchant_id.
    """
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = None
    
    # 1. Try Authorization Header
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        
    # 2. Try HttpOnly Cookie (Fallback)
    if not token:
        token = request.cookies.get("auth_token")
        
    if not token:
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[ALGORITHM])
        merchant_id: str = payload.get("sub")
        
        if merchant_id is None:
            raise credentials_exception
            
        import logging
        logging.getLogger("app.auth").info(f"🔑 Authenticated Tenant: {merchant_id}")
        return merchant_id
        
    except JWTError:
        raise credentials_exception


async def get_current_agent(
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> dict:
    """
    Dependency to authenticate an Agent via JWT.
    Enforces that the token is an 'agent' type token.
    """
    credentials_exception = HTTPException(
        status_code=401,
        detail="Invalid agent credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not authorization or not authorization.startswith("Bearer "):
        raise credentials_exception

    token = authorization[7:]

    try:
        payload = jwt.decode(token, _get_secret_key(), algorithms=[ALGORITHM])
        
        # Verify it's an agent token
        if payload.get("type") != "agent":
             raise credentials_exception
             
        # Return the simplified context (acting as 'user' for the API)
        return {
            "client_id": payload.get("sub"),
            "agent_type": payload.get("agent_type"),
            "merchant_id": payload.get("merchant_id"),
            "scopes": payload.get("scopes", [])
        }
        
    except JWTError:
        raise credentials_exception
