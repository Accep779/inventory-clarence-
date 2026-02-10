"""
SQLAlchemy Models for Inventory Clearance Agent.

This package is organized by domain:
- base.py: Base class and mixins
- merchant.py: Merchant/store models
- product.py: Product, variant, and pricing models
- customer.py: Customer and RFM models
- order.py: Order and line item models
- inbox.py: Inbox items and notifications
- campaign.py: Campaigns, LLM usage, and ledger
- journey.py: Customer and merchant journeys
- audit.py: Audit logging and reversals
- dna.py: Store DNA and strategy templates
- auth.py: OAuth tokens, CIBA, and agent clients
- agent.py: Agent thoughts and reasoning
- governor.py: Risk policies and controls
- global_brain.py: Cross-tenant learning

For backward compatibility, all models are re-exported from this module.
"""

# Base
from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, VersionMixin

# Core domain models
from app.models.merchant import Merchant
from app.models.product import Product, ProductVariant, FloorPricing
from app.models.customer import Customer
from app.models.order import Order, OrderItem

# Inbox and campaigns
from app.models.inbox import InboxItem, PendingNotification
from app.models.campaign import Campaign, LLMUsageLog, Ledger

# Journeys
from app.models.journey import CommercialJourney, MerchantJourney, TouchLog

# Audit and compliance
from app.models.audit import AuditLog, ActionReversal

# Store DNA and identity
from app.models.dna import StoreDNA, StrategyTemplate

# Authentication and authorization
from app.models.auth import (
    TokenVault,
    AsyncAuthorizationRequest,
    MerchantScopeGrant,
    AgentClient,
    IntegrationCredential,
)

# Agent reasoning
from app.models.agent import AgentThought

# Governance
from app.models.governor import RiskPolicy

# Global learning
from app.models.global_brain import GlobalStrategyPattern


__all__ = [
    # Base
    "Base",
    "UUIDMixin",
    "TimestampMixin",
    "SoftDeleteMixin",
    "VersionMixin",

    # Core domain
    "Merchant",
    "Product",
    "ProductVariant",
    "FloorPricing",
    "Customer",
    "Order",
    "OrderItem",

    # Inbox and campaigns
    "InboxItem",
    "PendingNotification",
    "Campaign",
    "LLMUsageLog",
    "Ledger",

    # Journeys
    "CommercialJourney",
    "MerchantJourney",
    "TouchLog",

    # Audit
    "AuditLog",
    "ActionReversal",

    # DNA
    "StoreDNA",
    "StrategyTemplate",

    # Auth
    "TokenVault",
    "AsyncAuthorizationRequest",
    "MerchantScopeGrant",
    "AgentClient",
    "IntegrationCredential",

    # Agent
    "AgentThought",

    # Governor
    "RiskPolicy",

    # Global Brain
    "GlobalStrategyPattern",
]
