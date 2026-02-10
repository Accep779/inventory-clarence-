"""
BasePlatformAdapter — The universal interface for all e-commerce platforms.

Every supported platform implements this class. The core system (ExecutionAgent,
sync.py, webhooks, pricing tasks) never imports a platform-specific module.
It imports this interface and calls methods on it. The correct adapter is
resolved at runtime based on the merchant's registered platform.

This is the single contract that makes Cephly platform-agnostic.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime


# ---------------------------------------------------------------------------
# Standardized data models — platform-neutral
# These are what every adapter returns. No Shopify variants, no WooCommerce
# product_ids. Just clean, unified objects.
# ---------------------------------------------------------------------------

@dataclass
class PlatformProduct:
    """A product as seen by Cephly. Every adapter normalizes to this."""
    platform_product_id: str        # The ID on the external platform
    platform_variant_id: str        # The specific SKU/variant ID (e.g., specific size/color)
    title: str
    category: str
    current_price: Decimal
    cost_price: Decimal
    stock_quantity: int
    last_sold_at: Optional[datetime]
    image_url: Optional[str]


@dataclass
class PlatformCustomer:
    """A customer as seen by Cephly. Normalized across all platforms."""
    platform_customer_id: str
    email: str
    phone: Optional[str]
    total_orders: int
    total_spent: Decimal
    last_order_at: Optional[datetime]


@dataclass
class PriceUpdateResult:
    """Confirmation of a price update. Every adapter returns this."""
    success: bool
    platform_product_id: str
    platform_variant_id: str
    new_price: Decimal
    updated_at: datetime
    error_message: Optional[str] = None


@dataclass
class WebhookEvent:
    """A normalized event from any platform. Adapters translate raw
    platform webhooks into this format before the core system sees them."""
    event_type: str                 # "order.created", "product.updated", etc.
    merchant_id: str
    payload: Dict                   # Normalized payload — same keys regardless of platform (e.g., "id", "title", "variants")
    raw_payload: Dict               # Original platform payload (for debugging)
    received_at: datetime


class BasePlatformAdapter(ABC):
    """
    Abstract base class for all e-commerce platform adapters.

    Each method represents one capability the core system needs from
    a platform. Adapters implement these methods using the platform's
    native API. The core system never knows which platform it is
    talking to.
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Unique identifier: 'shopify', 'woocommerce', 'bigcommerce', 'wix', etc."""
        pass

    # --- Authentication & Setup ---

    @abstractmethod
    async def authenticate(self, auth_payload: Dict) -> Dict:
        """
        Complete the platform's authentication/install flow.

        Input:  Whatever the platform sends back after OAuth (varies by platform).
        Output: A normalized auth record containing:
                - access_token (or equivalent credential)
                - shop_id (or equivalent merchant identifier on the platform)
                - any other platform-specific data needed for future API calls

        The core system stores this output. It passes it back as context
        for every subsequent adapter call.
        """
        pass

    # --- Data Sync ---

    @abstractmethod
    async def sync_products(self, merchant_context: Dict) -> List[PlatformProduct]:
        """
        Import the full product catalog from the platform.

        Returns a list of PlatformProduct objects. The adapter handles
        pagination, rate limiting, and any platform-specific quirks
        (e.g., Shopify variants vs. WooCommerce product attributes).
        """
        pass

    @abstractmethod
    async def sync_customers(self, merchant_context: Dict) -> List[PlatformCustomer]:
        """
        Import the customer list from the platform.

        Returns a list of PlatformCustomer objects. Same contract as
        sync_products — pagination and rate limiting are the adapter's job.
        """
        pass

    # --- Price Management ---

    @abstractmethod
    async def get_product(
        self,
        merchant_context: Dict,
        platform_product_id: str,
        platform_variant_id: str,
    ) -> PlatformProduct:
        """
        Fetch a single product's current state from the platform.

        Used by the ExecutionAgent to confirm current price before
        updating, and by the revert task to verify reversion succeeded.
        """
        pass

    @abstractmethod
    async def update_price(
        self,
        merchant_context: Dict,
        platform_product_id: str,
        platform_variant_id: str,
        new_price: Decimal,
    ) -> PriceUpdateResult:
        """
        Write a new price to the platform.

        This is the most critical method. It is called by ExecutionAgent
        before any marketing message fires. It must be synchronous in
        effect — when it returns success, the price must be live on the
        storefront.

        On failure, return PriceUpdateResult with success=False and
        the error_message populated. Do NOT raise an exception —
        let the caller decide how to handle it.
        """
        pass

    # --- Webhooks ---

    @abstractmethod
    async def register_webhook(
        self,
        merchant_context: Dict,
        event_type: str,
        callback_url: str,
    ) -> bool:
        """
        Tell the platform to send events to Cephly's webhook endpoint.

        Each platform has a different way to register webhooks. The
        adapter abstracts this entirely.
        """
        pass

    @abstractmethod
    def parse_webhook(self, raw_payload: Dict, headers: Dict) -> WebhookEvent:
        """
        Translate a raw platform webhook into a normalized WebhookEvent.

        Also validates the webhook signature (each platform signs
        webhooks differently). If validation fails, raise an exception.
        The core system catches it and rejects the event.

        This method is synchronous — it runs in the webhook request
        handler before any async processing.
        """
        pass
