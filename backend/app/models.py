"""
SQLAlchemy Models - Backward Compatibility Wrapper.

WARNING: This file is deprecated. Models have been reorganized into a package.
Please update your imports to use the new structure:

    from app.models import Merchant, Product  # Still works (re-exported)
    from app.models.merchant import Merchant  # Preferred new style

The models package is organized by domain:
- app/models/base.py - Base class and mixins
- app/models/merchant.py - Merchant model
- app/models/product.py - Product, ProductVariant, FloorPricing
- app/models/customer.py - Customer model
- app/models/order.py - Order, OrderItem
- app/models/inbox.py - InboxItem, PendingNotification
- app/models/campaign.py - Campaign, LLMUsageLog, Ledger
- app/models/journey.py - CommercialJourney, MerchantJourney, TouchLog
- app/models/audit.py - AuditLog, ActionReversal
- app/models/dna.py - StoreDNA, StrategyTemplate
- app/models/auth.py - TokenVault, AsyncAuthorizationRequest, MerchantScopeGrant, AgentClient
- app/models/agent.py - AgentThought
- app/models/governor.py - RiskPolicy
- app/models/global_brain.py - GlobalStrategyPattern
"""

import warnings

# Emit deprecation warning
warnings.warn(
    "Importing from 'app.models' module is deprecated. "
    "Models are now in the 'app.models' package. "
    "Update imports to use 'from app.models import X' or 'from app.models.x import X'.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export all models from the new package for backward compatibility
from app.models import (
    # Base
    Base,
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
    VersionMixin,
    # Core domain
    Merchant,
    Product,
    ProductVariant,
    FloorPricing,
    Customer,
    Order,
    OrderItem,
    # Inbox and campaigns
    InboxItem,
    PendingNotification,
    Campaign,
    LLMUsageLog,
    Ledger,
    # Journeys
    CommercialJourney,
    MerchantJourney,
    TouchLog,
    # Audit
    AuditLog,
    ActionReversal,
    # DNA
    StoreDNA,
    StrategyTemplate,
    # Auth
    TokenVault,
    AsyncAuthorizationRequest,
    MerchantScopeGrant,
    AgentClient,
    IntegrationCredential,
    # Agent
    AgentThought,
    # Governor
    RiskPolicy,
    # Global Brain
    GlobalStrategyPattern,
)


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
