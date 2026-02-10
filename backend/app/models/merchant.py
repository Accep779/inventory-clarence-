"""
Merchant model - represents Shopify stores and their configuration.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, Text, Boolean, Integer, DateTime, Numeric, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Merchant(Base, UUIDMixin, TimestampMixin):
    """
    Represents a Shopify store connected to our system.
    Stores OAuth credentials and merchant settings.
    """
    __tablename__ = "merchants"

    shopify_domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    shopify_shop_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted in production
    store_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20))  # Captured from Shopify for SMS CIBA

    # Platform Agnosticism
    platform: Mapped[str] = mapped_column(String(50), default="shopify")  # 'shopify', 'woocommerce', 'bigcommerce'
    platform_shop_id: Mapped[Optional[str]] = mapped_column(String(100))  # Platform-specific shop identifier

    # External Channels - Enabled channels list (moved from JSON)
    external_channels_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Billing & Usage
    plan: Mapped[str] = mapped_column(String(50), default="trial")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False)

    # Agent Settings
    max_auto_discount: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.40"))
    max_auto_ad_spend: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("500.00"))

    # Safety & Budgets
    monthly_llm_budget: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("50.00"))
    current_llm_spend: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    budget_reset_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Onboarding Status
    sync_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, syncing, completed, failed

    # Governor (Autonomy) Settings
    governor_aggressive_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    governor_calibration_threshold: Mapped[int] = mapped_column(Integer, default=50)
    governor_trust_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.95"))

    # Feature Flags
    enable_multi_plan_strategy: Mapped[bool] = mapped_column(Boolean, default=False)

    # Cognitive DNA Status
    dna_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, analyzing, completed, failed

    # DEPRECATED: These fields are being migrated to TokenVault and IntegrationCredential
    # Keep for backward compatibility during migration period
    klaviyo_api_key: Mapped[Optional[str]] = mapped_column(Text)  # Migrate to TokenVault
    twilio_account_sid: Mapped[Optional[str]] = mapped_column(String(255))  # Migrate to TokenVault
    twilio_auth_token: Mapped[Optional[str]] = mapped_column(Text)  # Migrate to TokenVault

    # Relationships
    products: Mapped[List["Product"]] = relationship("Product", back_populates="merchant", cascade="all, delete-orphan")
    customers: Mapped[List["Customer"]] = relationship("Customer", back_populates="merchant", cascade="all, delete-orphan")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="merchant", cascade="all, delete-orphan")
    inbox_items: Mapped[List["InboxItem"]] = relationship("InboxItem", back_populates="merchant", cascade="all, delete-orphan")
    campaigns: Mapped[List["Campaign"]] = relationship("Campaign", back_populates="merchant", cascade="all, delete-orphan")
    dna: Mapped[Optional["StoreDNA"]] = relationship("StoreDNA", back_populates="merchant", cascade="all, delete-orphan")
    thoughts: Mapped[List["AgentThought"]] = relationship("AgentThought", back_populates="merchant", cascade="all, delete-orphan")

    # Auth & Integration Relationships
    token_vault_entries: Mapped[List["TokenVault"]] = relationship("TokenVault", back_populates="merchant", cascade="all, delete-orphan")
    integration_credentials: Mapped[List["IntegrationCredential"]] = relationship("IntegrationCredential", back_populates="merchant", cascade="all, delete-orphan")
    agent_clients: Mapped[List["AgentClient"]] = relationship("AgentClient", back_populates="merchant", cascade="all, delete-orphan")
    scope_grants: Mapped[List["MerchantScopeGrant"]] = relationship("MerchantScopeGrant", back_populates="merchant", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_merchant_domain", "shopify_domain"),
    )
