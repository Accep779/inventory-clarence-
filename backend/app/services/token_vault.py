"""
Token Vault Service
===================

Manages OAuth token lifecycle for upstream providers.
Implements Auth0's Token Vault pattern for secure credential management.

Features:
- Fernet symmetric encryption for tokens at rest
- Automatic token refresh with exponential backoff
- Merchant notification on permanent failures
- Graceful degradation (never breaks agent system)
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_maker
from app.models import TokenVault, Merchant

logger = logging.getLogger(__name__)


# Custom exceptions for refresh handling
class RefreshableError(Exception):
    """Transient error that can be retried."""
    pass


class PermanentRefreshError(Exception):
    """Permanent error that cannot be recovered."""
    pass


class TokenVaultService:
    """
    Manages OAuth token lifecycle for upstream providers.
    Implements Auth0's Token Vault pattern.
    """
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self._encryption_key = os.getenv('TOKEN_ENCRYPTION_KEY')
        
    @property
    def encryption_key(self) -> bytes:
        """Get encryption key, raising if not configured."""
        if not self._encryption_key:
            raise ValueError("TOKEN_ENCRYPTION_KEY environment variable not set")
        return self._encryption_key.encode() if isinstance(self._encryption_key, str) else self._encryption_key
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    async def get_access_token(self, provider: str) -> Optional[str]:
        """
        Get a valid access token, auto-refreshing if needed.
        
        Args:
            provider: The integration provider (shopify, klaviyo, twilio)
            
        Returns:
            Decrypted access token or None if not available
        """
        vault_entry = await self._get_vault_entry(provider)
        if not vault_entry:
            logger.debug(f"No token vault entry for {provider} / {self.merchant_id}")
            return None
        
        # Check if token is expired or near expiry (5 min buffer)
        if vault_entry.expires_at:
            if vault_entry.expires_at < datetime.utcnow() + timedelta(minutes=5):
                if vault_entry.refresh_token_encrypted:
                    logger.info(f"Token for {provider} expiring soon, refreshing...")
                    return await self._refresh_token(vault_entry)
                else:
                    vault_entry.status = "expired"
                    await self._save_vault_entry(vault_entry)
                    logger.warning(f"Token for {provider} expired and no refresh token available")
                    return None
        
        # Token is valid
        try:
            return self._decrypt(vault_entry.access_token_encrypted)
        except InvalidToken:
            logger.error(f"Failed to decrypt token for {provider} - data may be corrupted")
            return None
    
    async def store_token(
        self,
        provider: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
        scopes: Optional[List[str]] = None,
        connection_name: Optional[str] = None
    ) -> TokenVault:
        """
        Store or update OAuth tokens with encryption.
        
        Args:
            provider: Integration provider name
            access_token: The access token to encrypt and store
            refresh_token: Optional refresh token
            expires_in: Token lifetime in seconds
            scopes: List of granted OAuth scopes
            connection_name: Human-readable connection identifier
            
        Returns:
            The created/updated TokenVault entry
        """
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None
        
        async with async_session_maker() as session:
            # Check for existing entry
            result = await session.execute(
                select(TokenVault).where(
                    TokenVault.merchant_id == self.merchant_id,
                    TokenVault.provider == provider
                )
            )
            vault_entry = result.scalar_one_or_none()
            
            if vault_entry:
                # Update existing
                vault_entry.access_token_encrypted = self._encrypt(access_token)
                if refresh_token:
                    vault_entry.refresh_token_encrypted = self._encrypt(refresh_token)
                vault_entry.expires_at = expires_at
                vault_entry.scopes_granted = scopes
                vault_entry.status = "active"
                vault_entry.retry_attempts = 0
                vault_entry.last_error = None
                vault_entry.updated_at = datetime.utcnow()
            else:
                # Create new
                vault_entry = TokenVault(
                    merchant_id=self.merchant_id,
                    provider=provider,
                    connection_name=connection_name or f"{provider} connection",
                    access_token_encrypted=self._encrypt(access_token),
                    refresh_token_encrypted=self._encrypt(refresh_token) if refresh_token else None,
                    expires_at=expires_at,
                    scopes_granted=scopes,
                    status="active"
                )
                session.add(vault_entry)
            
            await session.commit()
            await session.refresh(vault_entry)
            
            logger.info(f"✅ Stored {provider} token for merchant {self.merchant_id}")
            return vault_entry
    
    async def revoke_token(self, provider: str) -> bool:
        """Mark a token as revoked (e.g., on app uninstall)."""
        vault_entry = await self._get_vault_entry(provider)
        if vault_entry:
            vault_entry.status = "revoked"
            vault_entry.access_token_encrypted = ""  # Clear for security
            vault_entry.refresh_token_encrypted = None
            await self._save_vault_entry(vault_entry)
            logger.info(f"🔒 Revoked {provider} token for merchant {self.merchant_id}")
            return True
        return False
    
    async def get_token_status(self, provider: str) -> Dict[str, Any]:
        """Get token status for monitoring/debugging."""
        vault_entry = await self._get_vault_entry(provider)
        if not vault_entry:
            return {"exists": False, "provider": provider}
        
        return {
            "exists": True,
            "provider": provider,
            "status": vault_entry.status,
            "expires_at": vault_entry.expires_at.isoformat() if vault_entry.expires_at else None,
            "last_refreshed_at": vault_entry.last_refreshed_at.isoformat() if vault_entry.last_refreshed_at else None,
            "scopes": vault_entry.scopes_granted,
            "retry_attempts": vault_entry.retry_attempts,
            "last_error": vault_entry.last_error
        }
    
    # =========================================================================
    # TOKEN REFRESH (with retry and failure notification)
    # =========================================================================
    
    async def _refresh_token(self, vault_entry: TokenVault) -> Optional[str]:
        """
        Execute token refresh with retry logic and failure handling.
        
        Implements exponential backoff and notifies merchant on permanent failure.
        """
        max_attempts = vault_entry.max_retry_attempts
        
        for attempt in range(max_attempts):
            try:
                new_access_token = await self._execute_refresh(vault_entry)
                
                # Success - reset retry state
                vault_entry.retry_attempts = 0
                vault_entry.status = "active"
                vault_entry.last_refreshed_at = datetime.utcnow()
                vault_entry.last_error = None
                await self._save_vault_entry(vault_entry)
                
                logger.info(f"✅ Token refresh successful for {vault_entry.provider}")
                return new_access_token
                
            except RefreshableError as e:
                # Transient error - retry with exponential backoff
                vault_entry.retry_attempts = attempt + 1
                backoff = vault_entry.retry_backoff_seconds * (2 ** attempt)
                vault_entry.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff)
                vault_entry.last_error = str(e)
                await self._save_vault_entry(vault_entry)
                
                logger.warning(f"Token refresh attempt {attempt + 1}/{max_attempts} failed: {e}")
                await asyncio.sleep(min(backoff, 30))  # Cap at 30s for immediate retries
                
            except PermanentRefreshError as e:
                # Permanent error - mark as failed and notify merchant
                vault_entry.status = "error"
                vault_entry.permanent_failure_at = datetime.utcnow()
                vault_entry.last_error = str(e)
                await self._save_vault_entry(vault_entry)
                
                if not vault_entry.merchant_notified_of_failure:
                    await self._notify_merchant_token_failure(vault_entry, str(e))
                    vault_entry.merchant_notified_of_failure = True
                    await self._save_vault_entry(vault_entry)
                
                logger.error(f"❌ Permanent token refresh failure for {vault_entry.provider}: {e}")
                return None
        
        # All retries exhausted
        vault_entry.status = "error"
        vault_entry.permanent_failure_at = datetime.utcnow()
        vault_entry.last_error = "Max retry attempts exceeded"
        await self._save_vault_entry(vault_entry)
        
        await self._notify_merchant_token_failure(vault_entry, "Max retry attempts exceeded")
        
        logger.error(f"❌ Token refresh exhausted all retries for {vault_entry.provider}")
        return None
    
    async def _execute_refresh(self, vault_entry: TokenVault) -> str:
        """
        Execute the actual OAuth refresh flow for a specific provider.
        
        Raises:
            RefreshableError: For transient errors (network, rate limit)
            PermanentRefreshError: For permanent errors (invalid refresh token)
        """
        provider = vault_entry.provider
        refresh_token = self._decrypt(vault_entry.refresh_token_encrypted)
        
        if provider == "shopify":
            return await self._refresh_shopify_token(refresh_token)
        elif provider == "klaviyo":
            # Klaviyo uses API keys, not OAuth refresh
            raise PermanentRefreshError("Klaviyo uses API keys - no refresh needed")
        elif provider == "twilio":
            # Twilio uses API keys, not OAuth refresh
            raise PermanentRefreshError("Twilio uses API keys - no refresh needed")
        else:
            raise PermanentRefreshError(f"Unknown provider: {provider}")
    
    async def _refresh_shopify_token(self, refresh_token: str) -> str:
        """Refresh Shopify access token using refresh token."""
        import httpx
        
        client_id = os.getenv("SHOPIFY_API_KEY")
        client_secret = os.getenv("SHOPIFY_API_SECRET")
        
        if not client_id or not client_secret:
            raise PermanentRefreshError("Shopify API credentials not configured")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://accounts.shopify.com/oauth/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": client_id,
                        "client_secret": client_secret
                    }
                )
                
                if response.status_code == 401:
                    raise PermanentRefreshError("Refresh token is invalid or expired")
                elif response.status_code == 429:
                    raise RefreshableError("Rate limited by Shopify")
                elif response.status_code >= 500:
                    raise RefreshableError(f"Shopify server error: {response.status_code}")
                
                response.raise_for_status()
                data = response.json()
                return data["access_token"]
                
        except httpx.NetworkError as e:
            raise RefreshableError(f"Network error: {e}")
        except httpx.TimeoutException:
            raise RefreshableError("Request timeout")
    
    # =========================================================================
    # MERCHANT NOTIFICATION
    # =========================================================================
    
    async def _notify_merchant_token_failure(self, vault_entry: TokenVault, error: str):
        """Send notification to merchant about token failure."""
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(Merchant).where(Merchant.id == self.merchant_id)
                )
                merchant = result.scalar_one_or_none()
                
                if not merchant:
                    logger.error(f"Cannot notify merchant {self.merchant_id} - not found")
                    return
                
                # Log for now - integrate with actual email service later
                logger.warning(
                    f"📧 MERCHANT NOTIFICATION NEEDED:\n"
                    f"  To: {merchant.email}\n"
                    f"  Subject: Action Required: {vault_entry.provider} Connection Failed\n"
                    f"  Body: Your {vault_entry.provider} connection needs to be reauthorized.\n"
                    f"  Error: {error}"
                )
                
                # TODO: Integrate with email service
                # from app.services.notifications.email import send_email
                # await send_email(
                #     to=merchant.email,
                #     subject=f"Action Required: {vault_entry.provider} Connection Failed",
                #     body=f"Your {vault_entry.provider} connection needs to be reauthorized. Error: {error}"
                # )
                
        except Exception as e:
            logger.error(f"Failed to notify merchant about token failure: {e}")
    
    # =========================================================================
    # ENCRYPTION
    # =========================================================================
    
    def _encrypt(self, plaintext: str) -> str:
        """Encrypt token using Fernet symmetric encryption."""
        if not plaintext:
            return ""
        f = Fernet(self.encryption_key)
        return f.encrypt(plaintext.encode()).decode()
    
    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt token."""
        if not ciphertext:
            return ""
        f = Fernet(self.encryption_key)
        return f.decrypt(ciphertext.encode()).decode()
    
    # =========================================================================
    # DATABASE HELPERS
    # =========================================================================
    
    async def _get_vault_entry(self, provider: str) -> Optional[TokenVault]:
        """Fetch vault entry for a provider."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(TokenVault).where(
                    TokenVault.merchant_id == self.merchant_id,
                    TokenVault.provider == provider
                )
            )
            return result.scalar_one_or_none()
    
    async def _save_vault_entry(self, vault_entry: TokenVault):
        """Save changes to a vault entry."""
        async with async_session_maker() as session:
            session.add(vault_entry)
            await session.merge(vault_entry)
            await session.commit()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def generate_encryption_key() -> str:
    """Generate a new Fernet encryption key (for setup)."""
    return Fernet.generate_key().decode()


async def get_expiring_tokens(hours_until_expiry: int = 1) -> List[TokenVault]:
    """Get all tokens expiring within the specified hours."""
    threshold = datetime.utcnow() + timedelta(hours=hours_until_expiry)
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(TokenVault).where(
                TokenVault.status == "active",
                TokenVault.expires_at.isnot(None),
                TokenVault.expires_at <= threshold,
                TokenVault.refresh_token_encrypted.isnot(None)
            )
        )
        return result.scalars().all()
