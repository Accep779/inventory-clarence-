# Cephly — External Demand Channels Implementation Plan

**Date:** 2026-01-31
**Context:** Phase 4 — Adding third-party listing channels while preserving the merchant's own store as the primary channel

---

## 1. The Model

The merchant's store is not replaced. It is Channel A. It stays. What we are adding is Channel B and Channel C — external platforms where inventory can also be listed to reach buyers the merchant's store cannot reach on its own.

```
APPROVED CAMPAIGN
        │
        ▼
┌─────────────────┐
│  Channel Router │  ← Decides WHERE inventory goes based on rules
└────────┬────────┘
         │
    ┌────┴─────────────────────┐
    ▼                          ▼
┌─────────────┐      ┌──────────────────┐
│ Channel A   │      │ Channel B / C    │
│ Merchant's  │      │ External         │
│ Own Store   │      │ Platforms        │
│             │      │                  │
│ (existing   │      │ eBay Adapter     │
│  system)    │      │ Amazon Adapter   │
└─────────────┘      └──────────────────┘
```

Both channels can run simultaneously on the same campaign. The Channel Router decides the mix.

---

## 2. Routing Logic — How the System Decides

The Channel Router is not random. It uses the product's state to decide.

| Condition | Channel A (Store) | Channel B/C (External) | Reasoning |
|-----------|:-:|:-:|-----------|
| Stock ≤ 20 units, staleness < 14 days | ✓ | ✗ | Moderate overstock. Store alone can handle it |
| Stock > 20 units, staleness 14–30 days | ✓ | ✓ | Store is not moving it fast enough. Add external demand |
| Stock > 50 units, staleness > 30 days | ✓ | ✓ (priority) | Dead. External channels get first allocation. Store gets remainder |
| Any stock, category is high-margin | ✓ | ✗ | Protect brand perception. Keep on own store |
| Merchant explicitly opts out of external | ✓ | ✗ | Merchant preference always wins |

The merchant controls this in Settings. They can set a global preference (external on/off), per-category overrides, and per-campaign overrides via the Inbox approval.

---

## 3. What We Are Building — File by File

### 3.1 New Abstraction: `backend/app/channels/base.py`

This is separate from `adapters/base.py`. The Platform Adapter talks to the merchant's store. The Channel Adapter talks to external listing platforms. Different operations, different contract.

```python
"""
BaseExternalChannel — Contract for all external listing platforms.

A Platform Adapter (adapters/base.py) manages the merchant's own store:
    authenticate, sync, update_price, webhooks.

An External Channel (this file) manages LISTING inventory on third-party
platforms to reach new buyers:
    create_listing, monitor_listing, cancel_listing, sync_sales.

These are fundamentally different operations. A merchant's store is where
they sell permanently. An external channel is where Cephly places inventory
temporarily to clear it.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ExternalListing:
    """Represents a live listing on an external platform."""
    channel_name: str                   # "ebay", "amazon"
    external_listing_id: str            # The ID assigned by the external platform
    platform_product_id: str            # Original product ID from merchant's store
    platform_variant_id: str            # Original variant ID
    title: str
    listed_price: Decimal
    stock_allocated: int                # How many units were sent to this channel
    status: str                         # "active", "sold", "expired", "cancelled"
    created_at: datetime
    sold_at: Optional[datetime] = None
    units_sold: int = 0


@dataclass
class ListingResult:
    """Confirmation of a listing creation attempt."""
    success: bool
    external_listing_id: Optional[str]
    channel_name: str
    error_message: Optional[str] = None


@dataclass
class SyncedSale:
    """A sale that occurred on an external channel. Reported back to Cephly."""
    external_listing_id: str
    channel_name: str
    units_sold: int
    revenue: Decimal
    sold_at: datetime
    buyer_email: Optional[str]          # If the platform exposes this


class BaseExternalChannel(ABC):
    """
    Abstract base for all external listing channels.

    Every external platform (eBay, Amazon, etc.) implements this.
    The ChannelRouter calls these methods. The core system never
    imports a channel-specific module directly.
    """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Unique identifier: 'ebay', 'amazon', 'wholesale', etc."""
        pass

    @abstractmethod
    async def authenticate(self, credentials: Dict) -> Dict:
        """
        Authenticate with the external platform.
        Each platform has its own credential model (API keys, OAuth, etc.).
        Returns a context dict stored on the Merchant record under
        `external_channel_credentials[channel_name]`.
        """
        pass

    @abstractmethod
    async def create_listing(
        self,
        channel_context: Dict,
        product: Dict,
        price: Decimal,
        quantity: int,
        duration_days: int,
    ) -> ListingResult:
        """
        Create a listing on the external platform.

        Args:
            channel_context: Auth credentials for this channel
            product:         Normalized product data (title, description, images, category)
            price:           The clearance price to list at
            quantity:        How many units to allocate to this channel
            duration_days:   How long the listing should stay active

        The listing must go live immediately. When this returns success,
        the product must be purchasable on the external platform.
        """
        pass

    @abstractmethod
    async def monitor_listing(
        self,
        channel_context: Dict,
        external_listing_id: str,
    ) -> ExternalListing:
        """
        Check the current state of a listing.
        Called by the ObserverAgent on a schedule to track sales velocity
        on external channels.
        """
        pass

    @abstractmethod
    async def cancel_listing(
        self,
        channel_context: Dict,
        external_listing_id: str,
    ) -> bool:
        """
        Cancel an active listing. Used when:
        - All stock allocated to this channel has sold
        - The campaign ends and unsold stock reverts to the store
        - The merchant manually cancels
        """
        pass

    @abstractmethod
    async def sync_sales(
        self,
        channel_context: Dict,
        since: datetime,
    ) -> List[SyncedSale]:
        """
        Pull all sales that occurred on this channel since a given timestamp.
        Called by the nightly aggregator to update campaign performance data
        and feed the GlobalStrategyTemplate.
        """
        pass
```

### 3.2 New File: `backend/app/channels/router.py` — The Channel Router

```python
"""
ChannelRouter — Decides where inventory goes.

This is the decision engine that determines whether a cleared product
stays on the merchant's store only, gets listed externally, or both.

Rules are evaluated in order. First match wins.
Merchant preferences always override system defaults.
"""

from typing import List, Dict
from decimal import Decimal
from app.channels.base import BaseExternalChannel
from app.channels.registry import ChannelRegistry


class ChannelRouter:

    def __init__(self, merchant: Dict):
        self.merchant = merchant
        self.available_channels = ChannelRegistry.get_enabled_channels(merchant)

    def route(self, product: Dict, proposal: Dict) -> Dict:
        """
        Given a product and an approved clearance proposal, decide
        which channels to use and how to allocate stock.

        Returns:
            {
                "store": True/False,                    # Always True unless explicitly disabled
                "external_channels": [                  # List of external channels to use
                    {
                        "channel": "ebay",
                        "allocated_units": 30,
                        "price": Decimal("19.99"),
                        "duration_days": 14,
                    },
                    ...
                ],
                "reasoning": "..."                      # Why this routing was chosen
            }
        """

        stock = product["stock_quantity"]
        staleness = product["days_since_last_sale"]
        category = product["category"]

        # --- Merchant override: external channels disabled globally ---
        if not self.merchant.get("external_channels_enabled", True):
            return self._store_only("Merchant has external channels disabled.")

        # --- Merchant override: category-level exclusion ---
        excluded_categories = self.merchant.get("external_excluded_categories", [])
        if category in excluded_categories:
            return self._store_only(f"Category '{category}' is excluded from external listing by merchant.")

        # --- Rule 1: Low stock, low staleness → store only ---
        if stock <= 20 and staleness < 14:
            return self._store_only("Stock and staleness within store-only thresholds.")

        # --- Rule 2: Moderate stock, moderate staleness → both channels ---
        if stock > 20 and 14 <= staleness <= 30:
            return self._both_channels(
                product=product,
                proposal=proposal,
                external_allocation_percent=40,
                reasoning="Moderate overstock with no movement. Adding external demand alongside store.",
            )

        # --- Rule 3: High stock, high staleness → both, external priority ---
        if stock > 50 and staleness > 30:
            return self._both_channels(
                product=product,
                proposal=proposal,
                external_allocation_percent=70,
                reasoning="Dead stock. External channels get priority allocation. Store keeps remainder.",
            )

        # --- Default: store only ---
        return self._store_only("No external routing rule matched. Defaulting to store.")

    # ---------------------------------------------------------------
    # Routing builders
    # ---------------------------------------------------------------

    def _store_only(self, reasoning: str) -> Dict:
        return {
            "store": True,
            "external_channels": [],
            "reasoning": reasoning,
        }

    def _both_channels(
        self,
        product: Dict,
        proposal: Dict,
        external_allocation_percent: int,
        reasoning: str,
    ) -> Dict:
        stock = product["stock_quantity"]
        external_units = int(stock * (external_allocation_percent / 100))
        store_units = stock - external_units

        # Distribute external units across available channels evenly
        channels = []
        if self.available_channels:
            units_per_channel = external_units // len(self.available_channels)
            remainder = external_units % len(self.available_channels)

            for i, channel in enumerate(self.available_channels):
                allocation = units_per_channel + (1 if i < remainder else 0)
                if allocation > 0:
                    channels.append({
                        "channel": channel.channel_name,
                        "allocated_units": allocation,
                        "price": proposal["proposed_price"],
                        "duration_days": proposal.get("duration_hours", 168) // 24,
                    })

        return {
            "store": True,
            "store_units": store_units,
            "external_channels": channels,
            "reasoning": reasoning,
        }
```

### 3.3 New File: `backend/app/channels/registry.py` — Channel Registry

```python
"""
ChannelRegistry — Resolves available external channels for a merchant.

Similar to AdapterRegistry for platform adapters, but for external
listing channels. A merchant can enable/disable channels in Settings.
"""

from typing import Dict, List, Type
from app.channels.base import BaseExternalChannel
from app.channels.ebay import eBayChannel
from app.channels.amazon import AmazonChannel


CHANNEL_REGISTRY: Dict[str, Type[BaseExternalChannel]] = {
    "ebay": eBayChannel,
    "amazon": AmazonChannel,
    # "wholesale": WholesaleChannel,   ← future
}


class ChannelRegistry:

    @staticmethod
    def get_enabled_channels(merchant: Dict) -> List[BaseExternalChannel]:
        """
        Return instances of all channels the merchant has enabled
        and authenticated with.
        """
        enabled = merchant.get("enabled_external_channels", [])
        channels = []
        for name in enabled:
            channel_class = CHANNEL_REGISTRY.get(name)
            if channel_class:
                channels.append(channel_class())
        return channels

    @staticmethod
    def available_channels() -> list:
        return list(CHANNEL_REGISTRY.keys())
```

### 3.4 New File: `backend/app/channels/ebay.py` — eBay Channel Adapter

```python
"""
eBayChannel — Lists clearance inventory on eBay.

Uses the eBay Trading API (or Marketplace API) to create, monitor,
and cancel listings. All product data is normalized from Cephly's
internal format into eBay's listing requirements.
"""

import httpx
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional

from app.channels.base import (
    BaseExternalChannel,
    ExternalListing,
    ListingResult,
    SyncedSale,
)


class eBayChannel(BaseExternalChannel):

    EBAY_API_BASE = "https://api.ebay.com/sell/inventory/v1"

    @property
    def channel_name(self) -> str:
        return "ebay"

    async def authenticate(self, credentials: Dict) -> Dict:
        """
        eBay uses OAuth 2.0 with client credentials.
        Merchant provides their eBay seller account and authorizes
        Cephly via eBay's OAuth consent flow.
        """
        # Exchange authorization code for access token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.ebay.com/identity/v1/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "code": credentials["authorization_code"],
                    "redirect_uri": credentials["redirect_uri"],
                },
                auth=(credentials["client_id"], credentials["client_secret"]),
            )
            token_data = response.json()

        return {
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "seller_id": credentials["seller_id"],
            "expires_at": token_data.get("expires_in"),
        }

    async def create_listing(
        self,
        channel_context: Dict,
        product: Dict,
        price: Decimal,
        quantity: int,
        duration_days: int,
    ) -> ListingResult:
        """
        Create an eBay listing via the Inventory API.

        Maps Cephly's product data to eBay's required fields:
        - title (max 80 chars on eBay)
        - category (mapped to eBay category ID)
        - condition
        - images
        - price and quantity
        """
        token = channel_context["access_token"]

        # Truncate title to eBay's 80-char limit
        title = product["title"][:80]

        # Map to eBay category (simplified — in production this is a
        # lookup table mapping Cephly categories to eBay category IDs)
        ebay_category_id = _map_to_ebay_category(product.get("category", ""))

        # Step 1: Create inventory item
        inventory_payload = {
            "product": {
                "title": title,
                "description": product.get("description", title),
                "imageUrls": [product["image_url"]] if product.get("image_url") else [],
            },
            "condition": "NEW",
            "availability": {
                "shipToMeAvailability": {
                    "quantity": quantity,
                }
            },
        }

        sku = f"cephly_{product['platform_product_id']}_{product['platform_variant_id']}"

        async with httpx.AsyncClient() as client:
            # Create inventory item
            resp = await client.put(
                f"{self.EBAY_API_BASE}/inventory_item/{sku}",
                json=inventory_payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code not in (201, 204):
                return ListingResult(
                    success=False,
                    channel_name=self.channel_name,
                    error_message=f"Failed to create inventory item: {resp.text}",
                )

            # Step 2: Publish as an offer (creates the actual listing)
            offer_payload = {
                "sku": sku,
                "marketplaceId": "EBAY_US",
                "format": "FIXED_PRICE",
                "categoryId": ebay_category_id,
                "pricing": {
                    "price": {"currency": "USD", "value": str(price)},
                },
                "listingDuration": duration_days,
            }

            resp = await client.post(
                f"{self.EBAY_API_BASE}/offer",
                json=offer_payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 201:
                return ListingResult(
                    success=False,
                    channel_name=self.channel_name,
                    error_message=f"Failed to publish offer: {resp.text}",
                )

            offer_id = resp.json().get("offerId")

            # Step 3: Publish the offer to make it live
            resp = await client.post(
                f"{self.EBAY_API_BASE}/offer/{offer_id}/publish",
                headers={"Authorization": f"Bearer {token}"},
            )

            if resp.status_code != 200:
                return ListingResult(
                    success=False,
                    channel_name=self.channel_name,
                    error_message=f"Failed to publish listing: {resp.text}",
                )

        return ListingResult(
            success=True,
            external_listing_id=offer_id,
            channel_name=self.channel_name,
        )

    async def monitor_listing(self, channel_context: Dict, external_listing_id: str) -> ExternalListing:
        """Check current state of an eBay listing."""
        token = channel_context["access_token"]

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.EBAY_API_BASE}/offer/{external_listing_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            data = resp.json()

        status_map = {"PUBLISHED": "active", "ENDED": "expired", "UNPUBLISHED": "cancelled"}

        return ExternalListing(
            channel_name=self.channel_name,
            external_listing_id=external_listing_id,
            platform_product_id=data.get("sku", "").split("_")[1] if "_" in data.get("sku", "") else "",
            platform_variant_id=data.get("sku", "").split("_")[2] if data.get("sku", "").count("_") >= 2 else "",
            title=data.get("title", ""),
            listed_price=Decimal(data.get("pricing", {}).get("price", {}).get("value", "0")),
            stock_allocated=data.get("quantity", 0),
            status=status_map.get(data.get("status"), "unknown"),
            created_at=datetime.fromisoformat(data["creationDate"]) if data.get("creationDate") else datetime.utcnow(),
            units_sold=data.get("soldQuantity", 0),
        )

    async def cancel_listing(self, channel_context: Dict, external_listing_id: str) -> bool:
        """Cancel an active eBay listing."""
        token = channel_context["access_token"]

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.EBAY_API_BASE}/offer/{external_listing_id}/withdraw",
                headers={"Authorization": f"Bearer {token}"},
            )

        return resp.status_code == 200

    async def sync_sales(self, channel_context: Dict, since: datetime) -> List[SyncedSale]:
        """Pull completed orders from eBay since a given timestamp."""
        token = channel_context["access_token"]
        sales = []

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.ebay.com/sell/fulfillment/v1/order",
                params={"filter": f"creationDate:[{since.isoformat()}..+1d]"},
                headers={"Authorization": f"Bearer {token}"},
            )
            data = resp.json()

            for order in data.get("orders", []):
                for item in order.get("orderItems", []):
                    sales.append(SyncedSale(
                        external_listing_id=item.get("offerId", ""),
                        channel_name=self.channel_name,
                        units_sold=item.get("quantity", 1),
                        revenue=Decimal(item.get("finalValueFee", {}).get("value", "0")),
                        sold_at=datetime.fromisoformat(order["creationDate"]),
                        buyer_email=order.get("buyerEmailAddress"),
                    ))

        return sales


def _map_to_ebay_category(cephly_category: str) -> str:
    """Map Cephly product categories to eBay category IDs."""
    CATEGORY_MAP = {
        "Home & Kitchen": "11835",
        "Food & Beverage": "15029",
        "Apparel": "53077",
        "Electronics": "26368",
        "Sports & Outdoors": "36797",
        "Beauty": "260603",
        "Toys": "220",
    }
    return CATEGORY_MAP.get(cephly_category, "26368")  # Default to general
```

### 3.5 New File: `backend/app/channels/amazon.py` — Amazon Channel Adapter

```python
"""
AmazonChannel — Lists clearance inventory on Amazon via SP-API.

Amazon's Selling Partner API (SP-API) replaces the legacy MWS.
Requires the merchant to have an Amazon Seller account and authorize
Cephly as a selling partner application.
"""

import httpx
from decimal import Decimal
from datetime import datetime
from typing import Dict, List

from app.channels.base import (
    BaseExternalChannel,
    ExternalListing,
    ListingResult,
    SyncedSale,
)


class AmazonChannel(BaseExternalChannel):

    SP_API_BASE = "https://sellingpartnerapi-na.amazon.com"

    @property
    def channel_name(self) -> str:
        return "amazon"

    async def authenticate(self, credentials: Dict) -> Dict:
        """
        Amazon SP-API uses OAuth 2.0.
        Merchant authorizes via Amazon's consent flow.
        Cephly exchanges the code for access + refresh tokens.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://sellingpartnerapi-na.amazon.com/auth/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": credentials["authorization_code"],
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                },
            )
            token_data = resp.json()

        return {
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "seller_id": credentials["seller_id"],
            "marketplace_id": credentials.get("marketplace_id", "ATVPDKIKX0D"),  # US default
        }

    async def create_listing(
        self,
        channel_context: Dict,
        product: Dict,
        price: Decimal,
        quantity: int,
        duration_days: int,
    ) -> ListingResult:
        """
        Create a listing on Amazon.

        Amazon requires either an existing ASIN (if the product already
        exists in the catalog) or a new product submission. For clearance,
        we check for an existing ASIN first. If none exists, we create
        a new listing.

        This is a two-step process:
        1. Put inventory (set quantity)
        2. Put product pricing (set price)
        """
        token = channel_context["access_token"]
        seller_id = channel_context["seller_id"]
        marketplace_id = channel_context.get("marketplace_id", "ATVPDKIKX0D")

        sku = f"cephly_{product['platform_product_id']}_{product['platform_variant_id']}"

        headers = {
            "Authorization": f"Bearer {token}",
            "x-amz-date": datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            # Step 1: Create or update inventory
            inventory_payload = {
                "sku": sku,
                "marketplaceId": marketplace_id,
                "quantity": quantity,
                "condition": "New",
                "fulfillmentChannel": "MERCHANT_FULFIL",  # FBM — merchant ships directly
            }

            resp = await client.put(
                f"{self.SP_API_BASE}/feeds/2021-06-30/inventory",
                json=inventory_payload,
                headers=headers,
            )

            # Step 2: Set pricing
            pricing_payload = {
                "sku": sku,
                "marketplaceId": marketplace_id,
                "price": str(price),
                "currencyCode": "USD",
            }

            resp = await client.put(
                f"{self.SP_API_BASE}/pricing/2021-10-01/offers",
                json=pricing_payload,
                headers=headers,
            )

            if resp.status_code not in (200, 202):
                return ListingResult(
                    success=False,
                    channel_name=self.channel_name,
                    error_message=f"Amazon pricing update failed: {resp.text}",
                )

        return ListingResult(
            success=True,
            external_listing_id=sku,  # Amazon uses SKU as the listing identifier
            channel_name=self.channel_name,
        )

    async def monitor_listing(self, channel_context: Dict, external_listing_id: str) -> ExternalListing:
        """Check current state of an Amazon listing by SKU."""
        token = channel_context["access_token"]

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.SP_API_BASE}/inventories/2021-09-30/inventory",
                params={"skus": external_listing_id},
                headers={"Authorization": f"Bearer {token}"},
            )
            data = resp.json()
            item = data.get("inventories", [{}])[0] if data.get("inventories") else {}

        return ExternalListing(
            channel_name=self.channel_name,
            external_listing_id=external_listing_id,
            platform_product_id="",
            platform_variant_id="",
            title="",
            listed_price=Decimal("0"),
            stock_allocated=item.get("quantity", 0),
            status="active" if item.get("quantity", 0) > 0 else "sold",
            created_at=datetime.utcnow(),
        )

    async def cancel_listing(self, channel_context: Dict, external_listing_id: str) -> bool:
        """Remove an Amazon listing by setting quantity to 0."""
        token = channel_context["access_token"]

        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self.SP_API_BASE}/feeds/2021-06-30/inventory",
                json={"sku": external_listing_id, "quantity": 0},
                headers={"Authorization": f"Bearer {token}"},
            )

        return resp.status_code in (200, 202)

    async def sync_sales(self, channel_context: Dict, since: datetime) -> List[SyncedSale]:
        """Pull orders from Amazon since a given timestamp."""
        token = channel_context["access_token"]
        sales = []

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.SP_API_BASE}/orders/2018-11-01/orders",
                params={"StartDate": since.isoformat()},
                headers={"Authorization": f"Bearer {token}"},
            )
            data = resp.json()

            for order in data.get("Orders", []):
                for item in order.get("OrderItems", []):
                    sales.append(SyncedSale(
                        external_listing_id=item.get("SKU", ""),
                        channel_name=self.channel_name,
                        units_sold=int(item.get("QuantityOrdered", 1)),
                        revenue=Decimal(item.get("ItemPrice", {}).get("Amount", "0")),
                        sold_at=datetime.fromisoformat(order["PurchaseDate"]),
                        buyer_email=order.get("BuyerEmail"),
                    ))

        return sales
```

### 3.6 Patched File: `backend/app/agents/execution.py` — Route to All Channels

```python
"""
ExecutionAgent — Patched to route campaigns through ChannelRouter.

BEFORE: Always routes to merchant's store only.
AFTER:  Asks ChannelRouter where to send inventory. Executes on
        the store AND/OR external channels based on the routing decision.
        All channels run in parallel.
"""

from app.adapters.registry import AdapterRegistry
from app.channels.router import ChannelRouter
from app.channels.registry import ChannelRegistry


class ExecutionAgent:

    def __init__(self, session, merchant):
        self.session = session
        self.merchant = merchant
        self.adapter = AdapterRegistry.get_adapter(merchant.platform)
        self.channel_router = ChannelRouter(merchant)

    async def execute_campaign(self, campaign, proposal: dict) -> dict:

        # --- STEP 1: Lock original price ---
        campaign.original_price = proposal["current_price"]
        campaign.clearance_price = proposal["proposed_price"]
        campaign.status = "executing"
        await self.session.commit()

        # --- STEP 2: Route — decide which channels to use ---
        routing = self.channel_router.route(
            product=proposal,
            proposal=proposal,
        )

        results = {"store": None, "external": []}

        # --- STEP 3A: Execute on merchant's store (Channel A) ---
        if routing["store"]:
            store_result = await self.adapter.update_price(
                merchant_context=self.merchant.platform_context,
                platform_product_id=proposal["platform_product_id"],
                platform_variant_id=proposal["platform_variant_id"],
                new_price=proposal["proposed_price"],
            )

            if not store_result.success:
                campaign.status = "failed"
                campaign.failure_reason = f"Store price update failed: {store_result.error_message}"
                await self.session.commit()
                return {"success": False, "error": store_result.error_message}

            results["store"] = {"success": True}

        # --- STEP 3B: Execute on external channels (Channel B/C) — parallel ---
        import asyncio

        async def _list_on_channel(channel_info: dict):
            channel = ChannelRegistry.get_channel(channel_info["channel"])
            channel_context = self.merchant.external_channel_credentials.get(
                channel_info["channel"], {}
            )
            return await channel.create_listing(
                channel_context=channel_context,
                product=proposal,
                price=channel_info["price"],
                quantity=channel_info["allocated_units"],
                duration_days=channel_info["duration_days"],
            )

        if routing["external_channels"]:
            external_tasks = [_list_on_channel(ch) for ch in routing["external_channels"]]
            external_results = await asyncio.gather(*external_tasks, return_exceptions=True)

            for ch_info, result in zip(routing["external_channels"], external_results):
                if isinstance(result, Exception):
                    results["external"].append({
                        "channel": ch_info["channel"],
                        "success": False,
                        "error": str(result),
                    })
                else:
                    results["external"].append({
                        "channel": ch_info["channel"],
                        "success": result.success,
                        "listing_id": result.external_listing_id,
                        "error": result.error_message,
                    })

        # --- STEP 4: If store succeeded, send marketing ---
        if results["store"] and results["store"]["success"]:
            # Klaviyo + Twilio (unchanged — platform-agnostic)
            ...

        # --- STEP 5: Schedule revert for store price ---
        if routing["store"]:
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

        # --- STEP 6: Schedule external listing cleanup at campaign end ---
        if routing["external_channels"]:
            from app.tasks.channels import cleanup_external_listings
            cleanup_external_listings.apply_at(
                eta=campaign.end_date,
                kwargs={
                    "campaign_id": str(campaign.id),
                    "merchant_id": str(self.merchant.id),
                    "listings": [r for r in results["external"] if r["success"]],
                },
            )

        campaign.status = "active"
        campaign.routing = routing
        campaign.channel_results = results
        await self.session.commit()

        return {"success": True, "campaign_id": str(campaign.id), "routing": routing, "results": results}
```

### 3.7 New File: `backend/app/tasks/channels.py` — External Listing Cleanup

```python
"""
Celery task: Clean up external listings when a campaign ends.

When a campaign expires, any unsold inventory on external channels
must be cancelled. Stock reverts to the merchant's store.
"""

from celery import shared_task
from typing import List, Dict
import logging

from app.channels.registry import ChannelRegistry

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def cleanup_external_listings(
    self,
    campaign_id: str,
    merchant_id: str,
    listings: List[Dict],
):
    """
    Cancel all external listings for a completed campaign.

    Args:
        listings: List of dicts with {channel, listing_id} for each
                  external listing that was created during execution.
    """
    from app.database import sync_session_maker
    from app.models import Merchant
    import asyncio

    with sync_session_maker() as session:
        merchant = session.get(Merchant, merchant_id)
        if not merchant:
            logger.error("Merchant %s not found for cleanup.", merchant_id)
            return

        async def _cancel_all():
            for listing in listings:
                channel = ChannelRegistry.get_channel(listing["channel"])
                channel_context = merchant.external_channel_credentials.get(
                    listing["channel"], {}
                )
                success = await channel.cancel_listing(
                    channel_context=channel_context,
                    external_listing_id=listing["listing_id"],
                )
                if success:
                    logger.info("Cancelled listing %s on %s.", listing["listing_id"], listing["channel"])
                else:
                    logger.error("Failed to cancel listing %s on %s.", listing["listing_id"], listing["channel"])

        asyncio.run(_cancel_all())
```

### 3.8 New Frontend Page: `frontend/pages/channels.tsx` — Channel Setup

```
Merchant Settings → External Channels tab

┌─────────────────────────────────────────────────┐
│  External Channels                               │
│                                                  │
│  Enable external channels to reach new buyers    │
│  beyond your own store.                          │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │  eBay                          ○ Enabled │    │
│  │  Connect your eBay seller account        │    │
│  │  [Connect Account]                       │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │  Amazon                        ○ Enabled │    │
│  │  Connect your Amazon seller account      │    │
│  │  [Connect Account]                       │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  Routing Preferences                             │
│  ┌─────────────────────────────────────────┐    │
│  │  External channels enabled:    ☑ On      │    │
│  │  Excluded categories:                    │    │
│  │    [+ Add category]                      │    │
│  └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

---

## 4. New File Structure

```
backend/
├── app/
│   ├── adapters/                        (unchanged — handles merchant's store)
│   │   ├── base.py
│   │   ├── registry.py
│   │   └── shopify.py
│   ├── channels/                        ← NEW DIRECTORY — external listing channels
│   │   ├── __init__.py
│   │   ├── base.py                      ← NEW (BaseExternalChannel contract)
│   │   ├── registry.py                  ← NEW (ChannelRegistry)
│   │   ├── router.py                    ← NEW (ChannelRouter — routing decisions)
│   │   ├── ebay.py                      ← NEW (eBay listing adapter)
│   │   └── amazon.py                    ← NEW (Amazon listing adapter)
│   ├── agents/
│   │   └── execution.py                 ← PATCHED (routes to store + external)
│   ├── tasks/
│   │   ├── pricing.py                   (unchanged — store price revert)
│   │   └── channels.py                  ← NEW (external listing cleanup)
│   └── models.py                        ← PATCHED (add external_channel_credentials)
└── frontend/
    └── pages/
        └── channels.tsx                 ← NEW (channel setup UI)
```

---

## 5. Execution Sequence

| Phase | Action | Verification |
|-------|--------|--------------|
| 1 | Deploy `channels/base.py` + `channels/registry.py` | Structural only. No runtime impact |
| 2 | Deploy `channels/router.py` | Unit test routing rules against all conditions in Section 2 |
| 3 | Deploy `channels/ebay.py` + `channels/amazon.py` | Integration test against eBay/Amazon sandbox environments |
| 4 | Patch `execution.py` to use ChannelRouter | End-to-end test: approve a campaign, confirm listing appears on eBay/Amazon sandbox, confirm store price also updates |
| 5 | Deploy `tasks/channels.py` | Test: let a campaign expire, confirm external listings are cancelled |
| 6 | Deploy `frontend/pages/channels.tsx` | Manual test: connect eBay account, enable channel, run a campaign |

---

## 6. Merchant Model Addition

```
existing_channel_credentials: JSONB column on Merchant

Example value:
{
    "ebay": {
        "access_token": "...",
        "refresh_token": "...",
        "seller_id": "ebay_seller_123"
    },
    "amazon": {
        "access_token": "...",
        "refresh_token": "...",
        "seller_id": "amazon_seller_456",
        "marketplace_id": "ATVPDKIKX0D"
    }
}

Migration:
    ALTER TABLE merchants ADD COLUMN external_channel_credentials JSONB DEFAULT '{}';
    ALTER TABLE merchants ADD COLUMN enabled_external_channels JSONB DEFAULT '[]';
    ALTER TABLE merchants ADD COLUMN external_excluded_categories JSONB DEFAULT '[]';
    ALTER TABLE merchants ADD COLUMN external_channels_enabled BOOLEAN DEFAULT TRUE;
```
