"""
Credential Provider Abstraction
===============================

Abstracts away the source of integration credentials (API keys vs OAuth tokens).
Supports per-tenant credential storage with fallback to environment variables.

SECURITY: Per-tenant credentials ensure true multi-tenant isolation.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict
from sqlalchemy.future import select
from app.database import async_session_maker
from app.models import Merchant

logger = logging.getLogger(__name__)


class CredentialProvider(ABC):
    """Abstract base class for credential retrieval."""
    
    @abstractmethod
    async def get_credentials(self, merchant_id: str, provider: str) -> Optional[Dict[str, str]]:
        """
        Retrieve credentials for a specific provider.
        
        Args:
            merchant_id: The merchant's UUID
            provider: 'klaviyo', 'twilio', 'shopify', etc.
            
        Returns:
            Dict of credentials (e.g. {'api_key': '...'}) or None if not configured.
        """
        pass


class DatabaseCredentialProvider(CredentialProvider):
    """
    Production Implementation: Fetches per-tenant credentials from Merchant model.
    Falls back to environment variables if merchant-specific credentials not set.
    """
    
    async def get_credentials(self, merchant_id: str, provider: str) -> Optional[Dict[str, str]]:
        async with async_session_maker() as session:
            result = await session.execute(
                select(Merchant).where(Merchant.id == merchant_id)
            )
            merchant = result.scalar_one_or_none()
            
            if not merchant:
                logger.warning(f"Merchant {merchant_id} not found when fetching credentials")
                return None
            
            if provider == 'shopify':
                return {
                    'access_token': merchant.access_token,
                    'shop_domain': merchant.shopify_domain
                }
                
            elif provider == 'klaviyo':
                # Priority: Merchant-specific > Environment variable
                api_key = merchant.klaviyo_api_key or os.getenv('KLAVIYO_API_KEY')
                if api_key:
                    if merchant.klaviyo_api_key:
                        logger.debug(f"Using merchant-specific Klaviyo key for {merchant_id}")
                    else:
                        logger.warning(f"Using global Klaviyo key for {merchant_id} - consider setting per-tenant key")
                    return {'api_key': api_key}
                return None

            elif provider == 'twilio':
                # Priority: Merchant-specific > Environment variables
                sid = merchant.twilio_account_sid or os.getenv('TWILIO_ACCOUNT_SID')
                token = merchant.twilio_auth_token or os.getenv('TWILIO_AUTH_TOKEN')
                
                if sid and token:
                    if merchant.twilio_account_sid:
                        logger.debug(f"Using merchant-specific Twilio credentials for {merchant_id}")
                    else:
                        logger.warning(f"Using global Twilio credentials for {merchant_id} - consider setting per-tenant credentials")
                    return {'sid': sid, 'token': token}
                return None
                
        return None


class TokenVaultCredentialProvider(CredentialProvider):
    """
    Production Implementation: Uses Token Vault for encrypted credential storage.
    
    Falls back to DatabaseCredentialProvider if Token Vault entry doesn't exist.
    This enables gradual migration from plaintext to encrypted storage.
    """
    
    def __init__(self):
        self._fallback = DatabaseCredentialProvider()
    
    async def get_credentials(self, merchant_id: str, provider: str) -> Optional[Dict[str, str]]:
        from app.services.token_vault import TokenVaultService
        
        vault = TokenVaultService(merchant_id)
        
        try:
            # Try Token Vault first
            access_token = await vault.get_access_token(provider)
            
            if access_token:
                logger.debug(f"Using Token Vault for {provider}/{merchant_id}")
                
                if provider == 'shopify':
                    # Still need shop_domain from Merchant
                    async with async_session_maker() as session:
                        result = await session.execute(
                            select(Merchant).where(Merchant.id == merchant_id)
                        )
                        merchant = result.scalar_one_or_none()
                        if merchant:
                            return {
                                'access_token': access_token,
                                'shop_domain': merchant.shopify_domain
                            }
                    return None
                    
                elif provider == 'klaviyo':
                    return {'api_key': access_token}
                    
                elif provider == 'twilio':
                    # Twilio token stored as JSON with sid and token
                    import json
                    try:
                        creds = json.loads(access_token)
                        return {'sid': creds['sid'], 'token': creds['token']}
                    except (json.JSONDecodeError, KeyError):
                        return {'token': access_token}
                        
                else:
                    return {'access_token': access_token}
            
            # Fall back to legacy provider
            logger.debug(f"Falling back to legacy provider for {provider}/{merchant_id}")
            return await self._fallback.get_credentials(merchant_id, provider)
            
        except Exception as e:
            logger.warning(f"Token Vault error, falling back: {e}")
            return await self._fallback.get_credentials(merchant_id, provider)


# Factory to get the configured provider
def get_credential_provider() -> CredentialProvider:
    """
    Get the configured credential provider.
    
    Use TOKEN_VAULT=true to enable encrypted Token Vault storage.
    Falls back to DatabaseCredentialProvider for backward compatibility.
    """
    use_vault = os.getenv('USE_TOKEN_VAULT', 'false').lower() == 'true'
    
    if use_vault:
        logger.info("Using TokenVaultCredentialProvider (encrypted)")
        return TokenVaultCredentialProvider()
    else:
        logger.debug("Using DatabaseCredentialProvider (legacy)")
        return DatabaseCredentialProvider()

