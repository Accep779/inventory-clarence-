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
import logging

from app.channels.base import (
    BaseExternalChannel,
    ExternalListing,
    ListingResult,
    SyncedSale,
)

logger = logging.getLogger(__name__)

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
                    "scope": "https://api.ebay.com/oauth/api_scope/sell.inventory https://api.ebay.com/oauth/api_scope/sell.fulfillment"
                },
                auth=(credentials["client_id"], credentials["client_secret"]),
            )
            if response.status_code != 200:
                raise ValueError(f"eBay Auth Failed: {response.text}")
                
            token_data = response.json()

        return {
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "seller_id": credentials.get("seller_id", "unknown"),
            "expires_in": token_data.get("expires_in"),
            "authenticated_at": datetime.utcnow().isoformat()
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
        token = channel_context.get("access_token")
        if not token:
             return ListingResult(False, None, self.channel_name, "Missing access token")

        # Truncate title to eBay's 80-char limit
        title = product.get("title", "")[:80]
        
        # Safe defaults
        desc = product.get("description") or title
        img = product.get("image_url")

        # Map to eBay category (simplified — in production this is a
        # lookup table mapping Cephly categories to eBay category IDs)
        ebay_category_id = self._map_to_ebay_category(product.get("category", ""))

        # Step 1: Create inventory item
        inventory_payload = {
            "product": {
                "title": title,
                "description": desc,
                "imageUrls": [img] if img else [],
            },
            "condition": "NEW",
            "availability": {
                "shipToMeAvailability": {
                    "quantity": quantity,
                }
            },
        }

        # Safe SKU generation
        pid = product.get('platform_product_id', 'unknown')
        vid = product.get('platform_variant_id', 'unknown')
        sku = f"cephly_{pid}_{vid}"

        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Content-Language": "en-US"
            }
            
            # Create inventory item
            resp = await client.put(
                f"{self.EBAY_API_BASE}/inventory_item/{sku}",
                json=inventory_payload,
                headers=headers,
            )
            if resp.status_code not in (200, 201, 204):
                return ListingResult(
                    success=False,
                    channel_name=self.channel_name,
                    error_message=f"Failed to create inventory item: {resp.text}",
                    external_listing_id=None
                )

            # Step 2: Publish as an offer (creates the actual listing)
            offer_payload = {
                "sku": sku,
                "marketplaceId": "EBAY_US",
                "format": "FIXED_PRICE",
                "categoryId": ebay_category_id,
                "pricingSummary": {
                    "price": {"currency": "USD", "value": str(price)},
                },
                "listingDuration": "GTC", # Days not supported in inventory API usually, GTC standard
                "listingPolicies": {
                     "fulfillmentPolicyId": channel_context.get("fulfillment_policy_id", "default"),
                     "paymentPolicyId": channel_context.get("payment_policy_id", "default"),
                     "returnPolicyId": channel_context.get("return_policy_id", "default"),
                },
                "merchantLocationKey": channel_context.get("merchant_location_key", "default")
            }

            resp = await client.post(
                f"{self.EBAY_API_BASE}/offer",
                json=offer_payload,
                headers=headers,
            )
            if resp.status_code not in (200, 201):
                return ListingResult(
                    success=False,
                    channel_name=self.channel_name,
                    error_message=f"Failed to create offer: {resp.text}",
                    external_listing_id=None
                )

            offer_id = resp.json().get("offerId")

            # Step 3: Publish the offer to make it live
            resp = await client.post(
                f"{self.EBAY_API_BASE}/offer/{offer_id}/publish",
                headers=headers,
            )

            if resp.status_code != 200:
                return ListingResult(
                    success=False,
                    channel_name=self.channel_name,
                    error_message=f"Failed to publish listing: {resp.text}",
                    external_listing_id=offer_id
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
            if resp.status_code != 200:
                 # Return dummy if failed to monitor
                 return ExternalListing(self.channel_name, external_listing_id, "", "", "Unknown", Decimal(0), 0, "unknown", datetime.utcnow())
                 
            data = resp.json()

        status_map = {"PUBLISHED": "active", "ENDED": "expired", "UNPUBLISHED": "cancelled"}
        
        sku = data.get("sku", "")
        parts = sku.split("_")
        pid = parts[1] if len(parts) > 1 else ""
        vid = parts[2] if len(parts) > 2 else ""

        return ExternalListing(
            channel_name=self.channel_name,
            external_listing_id=external_listing_id,
            platform_product_id=pid,
            platform_variant_id=vid,
            title=data.get("listing", {}).get("listingTitle", ""), # inventory API structure varies
            listed_price=Decimal(data.get("pricingSummary", {}).get("price", {}).get("value", "0")),
            stock_allocated=data.get("availableQuantity", 0),
            status=status_map.get(data.get("status"), "unknown"),
            created_at=datetime.utcnow(), # Creation date not always in offer details easily
            units_sold=0, # Need analytics API for sold count usually
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
            # Note: Fulfillment API needed for orders
            resp = await client.get(
                "https://api.ebay.com/sell/fulfillment/v1/order",
                params={"filter": f"creationdate:[{since.isoformat()}..]"},
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 200: return []
            
            data = resp.json()

            for order in data.get("orders", []):
                for item in order.get("lineItems", []):
                    sales.append(SyncedSale(
                        external_listing_id=item.get("sku", ""), # Or offerId if available
                        channel_name=self.channel_name,
                        units_sold=int(item.get("quantity", 1)),
                        revenue=Decimal(item.get("total", {}).get("value", "0")),
                        sold_at=datetime.fromisoformat(order["creationDate"].replace("Z", "+00:00")),
                        buyer_email=order.get("buyer", {}).get("taxDetails", {}).get("taxId"), # Email PII often restricted
                    ))

        return sales


    def _map_to_ebay_category(self, cephly_category: str) -> str:
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
