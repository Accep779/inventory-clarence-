# Cephly Multiagents — Platform Agnostification Migration Guide

**Date:** 2026-01-31
**Classification:** Internal — Engineering & Architecture
**Purpose:** Complete system map for migrating Cephly from Shopify-only to multi-platform e-commerce support

---

## 1. The Core Principle

Klaviyo works for any platform. Twilio works for any platform. The StrategyAgent, FloorPricing, all Skills, the Inbox workflow — none of these care what store the merchant is running. The only thing that is Shopify-specific is **how Cephly talks to the store**. The refactor does not touch business logic. It inserts an abstraction layer between the business logic and the store platform. Everything above that layer stays exactly the same. Everything below it becomes a pluggable adapter.

---

## 2. What Is Currently Shopify-Specific

This is the complete inventory. Every item here was confirmed across Phase 1, 2, and 3 documents. Nothing was assumed.

| # | File / Component | What It Does | Shopify-Specific? |
|---|-----------------|--------------|-------------------|
| 1 | `backend/app/routers/auth.py` | OAuth handshake to install the app | Yes — Shopify OAuth flow |
| 2 | `backend/app/config.py` | Defines `SHOPIFY_SCOPES` | Yes — Shopify permission model |
| 3 | `backend/app/services/sync.py` | Downloads Products + Customers from the store | Yes — Shopify API endpoints |
| 4 | `backend/app/services/shopify_service.py` | Reads and writes product prices | Yes — Shopify variant API |
| 5 | `backend/app/routers/webhooks.py` | Receives event notifications from the store | Yes — Shopify webhook format |
| 6 | `backend/app/agents/execution.py` | Calls ShopifyService before sending messages | Yes — direct dependency |
| 7 | `backend/app/tasks/pricing.py` | Reverts prices via ShopifyService | Yes — direct dependency |
| 8 | `frontend/pages/scan.tsx` | Post-install merchant dashboard | Partially — install UX is platform-specific |
| 9 | Klaviyo integration | Sends clearance emails | No — already platform-agnostic |
| 10 | Twilio integration | Sends clearance SMS | No — already platform-agnostic |
| 11 | StrategyAgent + all Skills | Decides what strategy to run | No — pure business logic |
| 12 | FloorPricing service | Enforces minimum price | No — pure math |
| 13 | Inbox workflow | Merchant approval gate | No — platform-independent |
| 14 | ObserverAgent | Monitors campaign results | No — reads from internal DB |

**Items 1–8 are the migration surface. Items 9–14 are untouched.**

---

## 3. The Abstraction Architecture

The refactor introduces one new layer: the **Platform Adapter**. It sits between the core system and any e-commerce platform. The core system never calls a platform directly again. It calls the adapter. The adapter knows how to translate that call into the correct API for whatever platform the merchant is on.

```
┌─────────────────────────────────────────────────────┐
│                  CORE SYSTEM (unchanged)             │
│  StrategyAgent → ExecutionAgent → Inbox → Observer  │
│  Skills → FloorPricing → Klaviyo → Twilio           │
└────────────────────┬────────────────────────────────┘
                     │ calls
                     ▼
┌─────────────────────────────────────────────────────┐
│            PLATFORM ADAPTER INTERFACE                │
│         (BasePlatformAdapter — abstract)             │
│                                                     │
│  authenticate()    → handles OAuth per platform     │
│  sync_products()   → imports product catalog        │
│  sync_customers()  → imports customer data          │
│  update_price()    → writes price to the store      │
│  get_product()     → reads a single product         │
│  register_webhook()→ sets up event listeners        │
│  parse_webhook()   → normalizes incoming events     │
└────────────────────┬────────────────────────────────┘
                     │ implemented by
          ┌──────────┼──────────────┬──────────────┐
          ▼          ▼              ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ Shopify  │ │  WooComm │ │  BigCom- │ │  Wix     │
│ Adapter  │ │  erce    │ │  merce   │ │  Adapter │
│          │ │ Adapter  │ │ Adapter  │ │          │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

---

## 4. The Migration — File by File

### 4.1 New File: `backend/app/adapters/base.py` — The Contract

This is the interface every platform adapter must implement. It defines exactly what the core system is allowed to ask a platform to do. Nothing more, nothing less.

```python
"""
BasePlatformAdapter — The universal interface for all e-commerce platforms.

Every supported platform implements this class. The core system (ExecutionAgent,
sync.py, webhooks, pricing tasks) never imports a platform-specific module.
It imports this interface and calls methods on it. The correct adapter is
resolved at runtime based on the merchant's registered platform.

This is the single contract that makes Cephly platform-agnostic.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
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
    platform_variant_id: str        # The specific SKU/variant ID
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
    payload: Dict                   # Normalized payload — same keys regardless of platform
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
```

### 4.2 New File: `backend/app/adapters/shopify.py` — Shopify Becomes an Adapter

The existing ShopifyService, auth logic, sync logic, and webhook handling all move here. The class implements BasePlatformAdapter. Nothing else in the codebase imports ShopifyService directly anymore.

```python
"""
ShopifyPlatformAdapter — Shopify implementation of BasePlatformAdapter.

This class consolidates ALL Shopify-specific code into one place:
  - OAuth authentication
  - Product and customer sync
  - Price read/write
  - Webhook registration and parsing

The core system never imports this file. It imports BasePlatformAdapter
and resolves the correct adapter at runtime via the AdapterRegistry.
"""

import hashlib
import hmac
import httpx
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional

from app.adapters.base import (
    BasePlatformAdapter,
    PlatformProduct,
    PlatformCustomer,
    PriceUpdateResult,
    WebhookEvent,
)


class ShopifyPlatformAdapter(BasePlatformAdapter):

    SHOPIFY_API_VERSION = "2024-01"
    REQUIRED_SCOPES = "read_products,write_products,read_orders,read_customers"

    @property
    def platform_name(self) -> str:
        return "shopify"

    # --- Authentication ---

    async def authenticate(self, auth_payload: Dict) -> Dict:
        """
        Complete Shopify OAuth. Exchanges the temp code for a permanent
        access token. Returns the normalized auth record.
        """
        shop = auth_payload["shop"]
        code = auth_payload["code"]
        client_id = auth_payload["client_id"]
        client_secret = auth_payload["client_secret"]

        url = f"https://{shop}/admin/oauth/access_token"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
            })
            data = response.json()

        return {
            "access_token": data["access_token"],
            "shop_id": shop,
            "associated_user_scope": data.get("associated_user_scope"),
        }

    # --- Data Sync ---

    async def sync_products(self, merchant_context: Dict) -> List[PlatformProduct]:
        """
        Pull the full product catalog from Shopify, paginating through all results.
        Normalizes each Shopify product+variant into a PlatformProduct.
        """
        shop = merchant_context["shop_id"]
        token = merchant_context["access_token"]
        products = []
        page_info = None

        async with httpx.AsyncClient() as client:
            while True:
                url = f"https://{shop}/admin/api/{self.SHOPIFY_API_VERSION}/products.json"
                params = {"limit": 250}
                if page_info:
                    params["page_info"] = page_info

                response = await client.get(
                    url,
                    params=params,
                    headers={"X-Shopify-Access-Token": token},
                )
                data = response.json()

                for product in data.get("products", []):
                    for variant in product.get("variants", []):
                        products.append(PlatformProduct(
                            platform_product_id=str(product["id"]),
                            platform_variant_id=str(variant["id"]),
                            title=product["title"],
                            category=product.get("product_type", "Uncategorized"),
                            current_price=Decimal(variant["price"]),
                            cost_price=Decimal(variant.get("cost", "0")),
                            stock_quantity=variant.get("inventory_quantity", 0),
                            last_sold_at=None,  # Shopify doesn't expose this directly — resolved via orders
                            image_url=product.get("images", [{}])[0].get("src"),
                        ))

                # Shopify uses Link header for pagination
                link_header = response.headers.get("Link", "")
                if 'rel="next"' in link_header:
                    page_info = link_header.split('page_info="')[1].split('"')[0]
                else:
                    break

        return products

    async def sync_customers(self, merchant_context: Dict) -> List[PlatformCustomer]:
        """Pull customer list from Shopify. Normalizes to PlatformCustomer."""
        shop = merchant_context["shop_id"]
        token = merchant_context["access_token"]
        customers = []

        async with httpx.AsyncClient() as client:
            url = f"https://{shop}/admin/api/{self.SHOPIFY_API_VERSION}/customers.json"
            response = await client.get(
                url,
                params={"limit": 250},
                headers={"X-Shopify-Access-Token": token},
            )
            data = response.json()

            for c in data.get("customers", []):
                customers.append(PlatformCustomer(
                    platform_customer_id=str(c["id"]),
                    email=c["email"],
                    phone=c.get("phone"),
                    total_orders=c.get("orders_count", 0),
                    total_spent=Decimal(c.get("total_spent", "0")),
                    last_order_at=datetime.fromisoformat(c["last_order_at"]) if c.get("last_order_at") else None,
                ))

        return customers

    # --- Price Management ---

    async def get_product(
        self,
        merchant_context: Dict,
        platform_product_id: str,
        platform_variant_id: str,
    ) -> PlatformProduct:
        """Fetch a single variant's current state from Shopify."""
        shop = merchant_context["shop_id"]
        token = merchant_context["access_token"]

        async with httpx.AsyncClient() as client:
            url = (
                f"https://{shop}/admin/api/{self.SHOPIFY_API_VERSION}"
                f"/products/{platform_product_id}/variants/{platform_variant_id}.json"
            )
            response = await client.get(url, headers={"X-Shopify-Access-Token": token})
            variant = response.json().get("variant", {})

        return PlatformProduct(
            platform_product_id=platform_product_id,
            platform_variant_id=platform_variant_id,
            title=variant.get("title", ""),
            category="",
            current_price=Decimal(variant.get("price", "0")),
            cost_price=Decimal(variant.get("cost", "0")),
            stock_quantity=variant.get("inventory_quantity", 0),
            last_sold_at=None,
            image_url=None,
        )

    async def update_price(
        self,
        merchant_context: Dict,
        platform_product_id: str,
        platform_variant_id: str,
        new_price: Decimal,
    ) -> PriceUpdateResult:
        """Write a new price to a Shopify product variant."""
        shop = merchant_context["shop_id"]
        token = merchant_context["access_token"]

        url = (
            f"https://{shop}/admin/api/{self.SHOPIFY_API_VERSION}"
            f"/products/{platform_product_id}/variants/{platform_variant_id}.json"
        )

        async with httpx.AsyncClient() as client:
            response = await client.put(
                url,
                json={"variant": {"id": platform_variant_id, "price": str(new_price)}},
                headers={
                    "X-Shopify-Access-Token": token,
                    "Content-Type": "application/json",
                },
            )

        if response.status_code != 200:
            return PriceUpdateResult(
                success=False,
                platform_product_id=platform_product_id,
                platform_variant_id=platform_variant_id,
                new_price=new_price,
                updated_at=datetime.utcnow(),
                error_message=f"Shopify returned {response.status_code}: {response.text}",
            )

        return PriceUpdateResult(
            success=True,
            platform_product_id=platform_product_id,
            platform_variant_id=platform_variant_id,
            new_price=new_price,
            updated_at=datetime.utcnow(),
        )

    # --- Webhooks ---

    async def register_webhook(
        self,
        merchant_context: Dict,
        event_type: str,
        callback_url: str,
    ) -> bool:
        """Register a webhook on Shopify for the given event type."""
        shop = merchant_context["shop_id"]
        token = merchant_context["access_token"]

        # Map normalized event types to Shopify topics
        SHOPIFY_TOPIC_MAP = {
            "order.created": "orders/create",
            "order.updated": "orders/update",
            "product.updated": "products/update",
            "product.deleted": "products/destroy",
        }

        topic = SHOPIFY_TOPIC_MAP.get(event_type)
        if not topic:
            return False

        url = f"https://{shop}/admin/api/{self.SHOPIFY_API_VERSION}/webhooks.json"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={"webhook": {"topic": topic, "address": callback_url, "format": "json"}},
                headers={"X-Shopify-Access-Token": token},
            )

        return response.status_code in (201, 422)  # 422 = already exists, which is fine

    def parse_webhook(self, raw_payload: Dict, headers: Dict) -> WebhookEvent:
        """
        Validate Shopify's HMAC signature and normalize the webhook payload.

        Shopify signs webhooks with X-Shopify-Hmac-Sha256. If validation
        fails, this raises an exception and the event is rejected.
        """
        signature = headers.get("X-Shopify-Hmac-Sha256", "")
        secret = headers.get("_shopify_webhook_secret", "")  # Injected by middleware

        import json
        computed = hmac.new(
            secret.encode("utf-8"),
            json.dumps(raw_payload).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(computed, signature):
            raise ValueError("Shopify webhook signature validation failed.")

        # Normalize the event type
        shopify_topic = headers.get("X-Shopify-Webhook-Id-Topic", "")
        TOPIC_MAP = {
            "orders/create": "order.created",
            "orders/update": "order.updated",
            "products/update": "product.updated",
            "products/destroy": "product.deleted",
        }

        return WebhookEvent(
            event_type=TOPIC_MAP.get(shopify_topic, "unknown"),
            merchant_id=raw_payload.get("shop_id", ""),
            payload=raw_payload,
            raw_payload=raw_payload,
            received_at=datetime.utcnow(),
        )
```

### 4.3 New File: `backend/app/adapters/registry.py` — Platform Resolution at Runtime

The core system does not know which platform a merchant is on. This registry figures it out and returns the correct adapter instance.

```python
"""
AdapterRegistry — Resolves the correct platform adapter for a given merchant.

When ExecutionAgent needs to update a price, it does not say
"call ShopifyService". It says "get me the adapter for this merchant"
and calls update_price() on whatever comes back.

This file is where new platforms are registered. Adding WooCommerce
support means adding one line here and one new adapter file.
Nothing else changes.
"""

from typing import Dict, Type
from app.adapters.base import BasePlatformAdapter
from app.adapters.shopify import ShopifyPlatformAdapter


# ---------------------------------------------------------------------------
# Platform registry. Add new platforms here.
# ---------------------------------------------------------------------------

PLATFORM_REGISTRY: Dict[str, Type[BasePlatformAdapter]] = {
    "shopify": ShopifyPlatformAdapter,
    # "woocommerce": WooCommercePlatformAdapter,   ← add when built
    # "bigcommerce": BigCommercePlatformAdapter,   ← add when built
    # "wix": WixPlatformAdapter,                   ← add when built
}


class AdapterRegistry:

    @staticmethod
    def get_adapter(platform_name: str) -> BasePlatformAdapter:
        """
        Return an instance of the correct adapter for the given platform.

        Raises:
            UnsupportedPlatformError if the platform is not in the registry.
        """
        adapter_class = PLATFORM_REGISTRY.get(platform_name)
        if adapter_class is None:
            raise UnsupportedPlatformError(
                f"Platform '{platform_name}' is not supported. "
                f"Supported platforms: {list(PLATFORM_REGISTRY.keys())}"
            )
        return adapter_class()

    @staticmethod
    def supported_platforms() -> list:
        """Return the list of currently supported platform names."""
        return list(PLATFORM_REGISTRY.keys())


class UnsupportedPlatformError(Exception):
    """Raised when a merchant's platform is not in the registry."""
    pass
```

### 4.4 New File: `backend/app/models_update.py` — Merchant Model Change

The Merchant model needs one new field: `platform`. This is how the system knows which adapter to use for each merchant.

```python
"""
Merchant model update — Add platform field.

This is a single-column migration. Existing Shopify merchants
get backfilled with platform="shopify" during deployment.
New merchants have platform set during the authentication flow.
"""

# Add to the existing Merchant model in models.py:

# NEW FIELD:
#   platform: str  →  "shopify", "woocommerce", "bigcommerce", "wix", etc.
#
# Migration:
#   ALTER TABLE merchants ADD COLUMN platform VARCHAR(50) NOT NULL DEFAULT 'shopify';
#
# This backfills all existing merchants as Shopify automatically.
# No manual data entry required.

# Also add to the Merchant model:
#   platform_context: Dict (JSON column)
#       Stores the auth record returned by BasePlatformAdapter.authenticate()
#       Contains access_token, shop_id, or equivalent per platform.
#       The adapter reads this context on every API call.
#
# Migration:
#   ALTER TABLE merchants ADD COLUMN platform_context JSONB;
```

### 4.5 Patched File: `backend/app/agents/execution.py` — Remove Direct ShopifyService Import

The ExecutionAgent no longer imports ShopifyService. It imports AdapterRegistry and asks it for the correct adapter.

```python
"""
ExecutionAgent — Patched to use AdapterRegistry instead of ShopifyService.

BEFORE:
    from app.services.shopify_service import ShopifyService
    self.shopify = ShopifyService(shop=merchant.shopify_shop_id)
    await self.shopify.update_variant_price(...)

AFTER:
    from app.adapters.registry import AdapterRegistry
    adapter = AdapterRegistry.get_adapter(merchant.platform)
    result = await adapter.update_price(
        merchant_context=merchant.platform_context,
        ...
    )
"""

from app.adapters.registry import AdapterRegistry


class ExecutionAgent:

    def __init__(self, session, merchant):
        self.session = session
        self.merchant = merchant
        self.adapter = AdapterRegistry.get_adapter(merchant.platform)

    async def execute_campaign(self, campaign, proposal: dict) -> dict:

        # --- STEP 1: Lock original price ---
        campaign.original_price = proposal["current_price"]
        campaign.clearance_price = proposal["proposed_price"]
        campaign.status = "executing"
        await self.session.commit()

        # --- STEP 2: Update price via adapter (platform-agnostic) ---
        result = await self.adapter.update_price(
            merchant_context=self.merchant.platform_context,
            platform_product_id=proposal["platform_product_id"],
            platform_variant_id=proposal["platform_variant_id"],
            new_price=proposal["proposed_price"],
        )

        if not result.success:
            campaign.status = "failed"
            campaign.failure_reason = result.error_message
            await self.session.commit()
            return {"success": False, "error": result.error_message}

        # --- STEP 3: Price confirmed live. Send marketing. ---
        # (Klaviyo and Twilio calls remain unchanged — already platform-agnostic)
        ...

        # --- STEP 4: Schedule revert ---
        from app.tasks.pricing import revert_campaign_pricing
        revert_campaign_pricing.apply_at(
            eta=campaign.end_date,
            kwargs={
                "campaign_id": str(campaign.id),
                "merchant_id": str(self.merchant.id),
                "platform_product_id": proposal["platform_product_id"],
                "platform_variant_id": proposal["platform_variant_id"],
                "original_price": str(campaign.original_price),
            },
        )

        campaign.status = "active"
        await self.session.commit()
        return {"success": True, "campaign_id": str(campaign.id)}
```

### 4.6 Patched File: `backend/app/tasks/pricing.py` — Revert Task Uses Adapter

```python
"""
revert_campaign_pricing — Patched to use AdapterRegistry.

The task no longer knows or cares what platform the merchant is on.
It loads the merchant record, gets the adapter, and calls update_price().
"""

from celery import shared_task
from decimal import Decimal
from datetime import datetime
import logging

from app.adapters.registry import AdapterRegistry

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=300)
def revert_campaign_pricing(
    self,
    campaign_id: str,
    merchant_id: str,
    platform_product_id: str,
    platform_variant_id: str,
    original_price: str,
):
    """Revert price. Platform-agnostic via AdapterRegistry."""

    from app.database import sync_session_maker
    from app.models import Merchant, Campaign

    with sync_session_maker() as session:
        merchant = session.get(Merchant, merchant_id)
        if not merchant:
            logger.error("Merchant %s not found for revert.", merchant_id)
            return

        adapter = AdapterRegistry.get_adapter(merchant.platform)

        # Note: update_price is async but Celery runs sync.
        # Use asyncio.run() or a sync wrapper here depending on your Celery async setup.
        import asyncio
        result = asyncio.run(adapter.update_price(
            merchant_context=merchant.platform_context,
            platform_product_id=platform_product_id,
            platform_variant_id=platform_variant_id,
            new_price=Decimal(original_price),
        ))

        if not result.success:
            logger.error("Revert failed for campaign %s: %s", campaign_id, result.error_message)
            raise self.retry(countdown=300 * (self.request.retries + 1))

        # Mark campaign completed
        campaign = session.get(Campaign, campaign_id)
        if campaign:
            campaign.status = "completed"
            campaign.completed_at = datetime.utcnow()
            session.commit()

        logger.info("Price reverted. campaign=%s merchant=%s", campaign_id, merchant_id)
```

### 4.7 Patched File: `backend/app/routers/auth.py` — Platform-Aware Auth

```python
"""
Auth router — Patched to support multiple platforms.

BEFORE: Hardcoded Shopify OAuth flow.
AFTER:  Accepts a `platform` parameter. Routes to the correct
        adapter's authenticate() method. Stores the result on
        the Merchant record.

The frontend install page passes ?platform=shopify (or woocommerce, etc.)
as part of the install URL. This router reads it and acts accordingly.
"""

from fastapi import APIRouter, Query
from app.adapters.registry import AdapterRegistry, UnsupportedPlatformError

router = APIRouter()


@router.get("/install")
async def install(platform: str = Query(...)):
    """
    Entry point for app installation.
    Redirects the merchant to the correct platform's OAuth page.
    """
    try:
        adapter = AdapterRegistry.get_adapter(platform)
    except UnsupportedPlatformError:
        return {"error": f"Platform '{platform}' is not supported."}

    # Each platform has its own OAuth URL structure.
    # The adapter could expose a method like `get_oauth_url()` if needed,
    # or this can be handled with a simple config map here.
    ...


@router.get("/callback")
async def oauth_callback(platform: str = Query(...), code: str = Query(...), shop: str = Query(None)):
    """
    Receives the OAuth callback from the platform.
    Passes everything to the adapter's authenticate() method.
    Stores the result on the Merchant record.
    """
    adapter = AdapterRegistry.get_adapter(platform)

    auth_record = await adapter.authenticate({
        "code": code,
        "shop": shop,                          # Shopify-specific, ignored by other adapters
        "client_id": "...",                     # From env config
        "client_secret": "...",                 # From env config
    })

    # Create or update Merchant record
    # merchant.platform = platform
    # merchant.platform_context = auth_record
    ...
```

### 4.8 Patched File: `backend/app/routers/webhooks.py` — Normalized Webhook Handling

```python
"""
Webhooks router — Patched to accept webhooks from any platform.

BEFORE: Hardcoded Shopify webhook parsing.
AFTER:  Accepts a `platform` path parameter. Routes to the correct
        adapter's parse_webhook() method. The rest of the system
        receives a normalized WebhookEvent regardless of source.
"""

from fastapi import APIRouter, Request
from app.adapters.registry import AdapterRegistry

router = APIRouter()


@router.post("/webhooks/{platform}")
async def receive_webhook(platform: str, request: Request):
    """
    Universal webhook endpoint.

    URL structure: /webhooks/shopify, /webhooks/woocommerce, etc.
    Each platform's webhook registration points to its own path.
    The adapter validates the signature and normalizes the payload.
    """
    adapter = AdapterRegistry.get_adapter(platform)

    raw_payload = await request.json()
    headers = dict(request.headers)

    try:
        event = adapter.parse_webhook(raw_payload, headers)
    except ValueError as e:
        # Signature validation failed
        return {"error": str(e)}, 401

    # From here, the event is a normalized WebhookEvent.
    # The rest of the system processes it identically regardless of platform.
    # Route to ObserverAgent, update campaign state, etc.
    ...

    return {"status": "received"}
```

---

## 5. New File Structure (Post-Migration)

```
backend/
├── app/
│   ├── adapters/                        ← NEW DIRECTORY
│   │   ├── __init__.py
│   │   ├── base.py                      ← NEW (BasePlatformAdapter contract)
│   │   ├── registry.py                  ← NEW (AdapterRegistry + platform resolution)
│   │   ├── shopify.py                   ← NEW (all Shopify code consolidated here)
│   │   ├── woocommerce.py              ← FUTURE (implements BasePlatformAdapter)
│   │   ├── bigcommerce.py              ← FUTURE
│   │   └── wix.py                       ← FUTURE
│   ├── agents/
│   │   ├── execution.py                 ← PATCHED (uses AdapterRegistry)
│   │   └── ...                          (unchanged)
│   ├── routers/
│   │   ├── auth.py                      ← PATCHED (platform-aware)
│   │   ├── webhooks.py                  ← PATCHED (universal endpoint)
│   │   └── ...                          (unchanged)
│   ├── services/
│   │   ├── shopify_service.py           ← DEPRECATED (logic moved to adapters/shopify.py)
│   │   └── ...                          (unchanged)
│   ├── tasks/
│   │   └── pricing.py                   ← PATCHED (uses AdapterRegistry)
│   └── models.py                        ← PATCHED (platform + platform_context fields)
└── tests/
    └── adapters/
        ├── test_shopify_adapter.py      ← NEW (unit tests for Shopify adapter)
        └── test_adapter_contract.py     ← NEW (contract tests — every adapter must pass)
```

---

## 6. What Adding a New Platform Looks Like

Once this architecture is in place, adding WooCommerce (or any other platform) is a four-step process:

**Step 1:** Create `backend/app/adapters/woocommerce.py`. Implement all methods of BasePlatformAdapter using WooCommerce's REST API.

**Step 2:** Register it in `registry.py` by adding one line to PLATFORM_REGISTRY.

**Step 3:** Run `test_adapter_contract.py` against the new adapter. This test suite validates that every method returns the correct types and behaves according to the contract. If it passes, the adapter is compatible with the core system.

**Step 4:** Update the frontend install page to include WooCommerce as an option.

That is it. No changes to ExecutionAgent, no changes to StrategyAgent, no changes to the Inbox, no changes to pricing tasks, no changes to Skills. The abstraction layer holds.

---

## 7. Migration Execution Order

| Phase | Action | What It Touches |
|-------|--------|-----------------|
| 1 | Deploy `adapters/base.py` + `adapters/registry.py` | New files only. No runtime impact |
| 2 | Deploy `adapters/shopify.py` | Consolidates existing Shopify code. No behavior change |
| 3 | Patch `execution.py` + `pricing.py` to use AdapterRegistry | Core behavior change. Test with existing Shopify merchants first |
| 4 | Patch `auth.py` + `webhooks.py` | Auth and webhook routing change. Test install flow end-to-end |
| 5 | Run DB migration (add `platform` + `platform_context` to Merchant) | Backfills existing merchants as `platform="shopify"` |
| 6 | Deprecate `shopify_service.py` | Confirm zero imports remain. Remove file |

---

## 8. Platforms to Target (Priority Order)

| Priority | Platform | Why | Estimated Effort |
|----------|----------|-----|-----------------|
| 1 | Shopify | Already built — becomes the first adapter | Done (refactor) |
| 2 | WooCommerce | Largest open-source e-commerce platform. Massive install base. REST API is well-documented | Medium |
| 3 | BigCommerce | Strong mid-market presence. API-first platform — cleanest integration path | Medium |
| 4 | Wix | Huge SMB base. Many small stores with exactly the dead inventory problem Cephly solves | Medium-High (Wix API is more restrictive) |
| 5 | Squarespace | Growing e-commerce presence. API access is newer and more limited | High |
| 6 | Magento / Adobe Commerce | Enterprise segment. Complex but high-value clients | High |
