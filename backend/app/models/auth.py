"""
Authentication and authorization models.
OAuth tokens, CIBA requests, and agent client identities.
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, DateTime, ForeignKey, Index, Text, JSON, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class TokenVault(Base, UUIDMixin, TimestampMixin):
    """
    Secure storage for OAuth tokens with lifecycle management.
    Implements Auth0's Token Vault pattern for encrypted credential storage.
    """
    __tablename__ = "token_vault"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)

    # Provider identification
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # shopify, klaviyo, twilio
    connection_name: Mapped[Optional[str]] = mapped_column(String(100))  # Human-readable name

    # Token storage (encrypted at rest)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    token_type: Mapped[str] = mapped_column(String(50), default="bearer")

    # Lifecycle management
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    refresh_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Scope tracking
    scopes_granted: Mapped[Optional[list]] = mapped_column(JSON)
    scopes_requested: Mapped[Optional[list]] = mapped_column(JSON)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, expired, revoked, error
    last_error: Mapped[Optional[str]] = mapped_column(Text)

    # Retry/failure handling
    retry_attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_retry_attempts: Mapped[int] = mapped_column(Integer, default=3)
    retry_backoff_seconds: Mapped[int] = mapped_column(Integer, default=60)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    permanent_failure_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    merchant_notified_of_failure: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="token_vault_entries")

    __table_args__ = (
        Index("idx_token_vault_merchant_provider", "merchant_id", "provider"),
        Index("idx_token_vault_status", "status"),
    )


class AsyncAuthorizationRequest(Base, UUIDMixin, TimestampMixin):
    """
    CIBA-style authorization request for high-risk agent operations.
    Implements Auth0's Async OAuth pattern.
    """
    __tablename__ = "async_auth_requests"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)

    # Request identification
    auth_req_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    inbox_item_id: Mapped[Optional[str]] = mapped_column(ForeignKey("inbox_items.id"))

    # Agent context
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)  # execution, strategy, reactivation
    operation_type: Mapped[str] = mapped_column(String(100), nullable=False)  # campaign_execute, discount_apply

    # Rich Authorization Request Details (RAR)
    authorization_details: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Lifecycle
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, pending_manual, approved, rejected, expired
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    decision_channel: Mapped[Optional[str]] = mapped_column(String(50))  # mobile_push, sms, email, dashboard

    # Notification tracking
    push_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sms_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    email_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    __table_args__ = (
        Index("idx_async_auth_merchant", "merchant_id"),
        Index("idx_async_auth_status", "status"),
        Index("idx_async_auth_inbox", "inbox_item_id"),
    )


class MerchantScopeGrant(Base, UUIDMixin, TimestampMixin):
    """
    Tracks which scopes a merchant has granted to each agent type.
    Enables fine-grained control over agent permissions.
    """
    __tablename__ = "merchant_scope_grants"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)

    # Scope definition
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)  # observer, strategy, execution, reactivation
    scope: Mapped[str] = mapped_column(String(100), nullable=False)  # The OAuth2-style scope string

    # Grant metadata
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    granted_by: Mapped[Optional[str]] = mapped_column(String(36))  # User ID who granted

    # Conditional grants - JSON conditions that must be met
    conditions: Mapped[Optional[dict]] = mapped_column(JSON)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    revoked_by: Mapped[Optional[str]] = mapped_column(String(36))

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="scope_grants")

    __table_args__ = (
        Index("idx_scope_grant_merchant_agent", "merchant_id", "agent_type"),
        Index("idx_scope_grant_scope", "scope"),
    )


class AgentClient(Base, UUIDMixin, TimestampMixin):
    """
    OAuth client credentials for each agent type.
    Enables distinct identity and authorization per agent.
    """
    __tablename__ = "agent_clients"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)

    # OAuth Client Credentials
    client_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    client_secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Agent type
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)  # observer, strategy, execution, reactivation

    # Scopes granted to this agent (cached from grants)
    allowed_scopes: Mapped[list] = mapped_column(JSON, default=list)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="agent_clients")

    __table_args__ = (
        Index("idx_agent_client_merchant", "merchant_id"),
        Index("idx_agent_client_client_id", "client_id"),
    )


class IntegrationCredential(Base, UUIDMixin, TimestampMixin):
    """
    Secure storage for external channel API credentials.

    Replaces the JSON external_channel_credentials field with:
    - Queryable structure
    - Encrypted credential values
    - Per-channel configuration
    - Audit trail of credential changes
    """
    __tablename__ = "integration_credentials"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)

    # Channel identification
    channel_type: Mapped[str] = mapped_column(String(50), nullable=False)  # ebay, amazon, etsy, walmart, etc.
    channel_name: Mapped[Optional[str]] = mapped_column(String(100))  # Human-readable name (e.g., "My eBay Store")
    environment: Mapped[str] = mapped_column(String(20), default="production")  # production, sandbox

    # Encrypted credential storage
    # Fields are encrypted at rest using Fernet (same as TokenVault)
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    api_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    access_token_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text)

    # OAuth-specific fields
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    scopes: Mapped[Optional[list]] = mapped_column(JSON)  # Granted scopes

    # Status and health
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, expired, revoked, error
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Configuration (JSON for flexibility)
    config: Mapped[Optional[dict]] = mapped_column(JSON, default={})  # Channel-specific settings
    # Example: {"marketplace_id": "EBAY_US", "region": "US"}

    # Excluded categories (moved from Merchant.external_excluded_categories)
    excluded_categories: Mapped[Optional[list]] = mapped_column(JSON, default=[])

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="integration_credentials")

    __table_args__ = (
        Index("idx_integration_cred_merchant_channel", "merchant_id", "channel_type"),
        Index("idx_integration_cred_status", "status"),
    )
