"""
AmazonChannel — Lists clearance inventory on Amazon via SP-API.

Amazon's Selling Partner API (SP-API) replaces the legacy MWS.
Requires the merchant to have an Amazon Seller account and authorize
Cephly as a selling partner application.
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
                "https://api.amazon.com/auth/o2/token",
                data={
                    "grant_type": "authorization_code",
                    "code": credentials["authorization_code"],
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                    "redirect_uri": credentials["redirect_uri"]
                },
            )
            if resp.status_code != 200:
                raise ValueError(f"Amazon Auth Failed: {resp.text}")
                
            token_data = resp.json()

        return {
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "seller_id": credentials.get("seller_id"), # Often passed directly or retrieved via profile API
            "marketplace_id": credentials.get("marketplace_id", "ATVPDKIKX0D"),  # US default
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
        Create a listing on Amazon.

        Amazon requires either an existing ASIN (if the product already
        exists in the catalog) or a new product submission. For clearance,
        we check for an existing ASIN first. If none exists, we create
        a new listing.

        This is a two-step process:
        1. Put inventory (set quantity)
        2. Put product pricing (set price)
        """
        token = channel_context.get("access_token")
        if not token:
             return ListingResult(False, None, self.channel_name, "Missing access token")

        marketplace_id = channel_context.get("marketplace_id", "ATVPDKIKX0D")

        # Use platform IDs to generate SKU
        pid = product.get('platform_product_id', 'unk')
        vid = product.get('platform_variant_id', 'unk')
        sku = f"cephly_{pid}_{vid}"

        headers = {
            "x-amz-access-token": token,
            "Content-Type": "application/json",
            "User-Agent": "Cephly/1.0"
        }

        async with httpx.AsyncClient() as client:
            # Step 1: Create or update inventory
            inventory_payload = {
                "sku": sku,
                "marketplaceId": marketplace_id,
                "productType": "PRODUCT", # Simplified
                "attributes": {
                    "condition": "new_new",
                    "fulfillment_availability": [
                        {
                            "fulfillment_channel_code": "DEFAULT",
                            "quantity": quantity
                        }
                    ]
                }
            }
            
            # Note: SP-API feeds/listings API is complex. 
            # Using Listings Items API (2021-08-01) PUT operation
            
            resp = await client.put(
                f"{self.SP_API_BASE}/listings/2021-08-01/items/{seller_id}/{sku}",
                json=inventory_payload,
                headers=headers,
                params={"marketplaceIds": marketplace_id} # Required param
            )

            # Step 2: Set pricing (might be separate depending on API version, 
            # Listings Items API handles both often, but let's assume separate Pricing API update for clarity/robustness)
            
            # However, Listings Items API is the modern way to do both.
            # If the PUT above succeeds, we might be good.
            # Let's ensure price is in the payload for Listings Items API.
            
            # Re-constructing payload to include price if using Listings Items API
            # But the guide implementation used separate endpoints (Inventory and Pricing).
            # I will stick to the guide's logical separation but use the modern endpoints where obvious or stick to guide structure.
            # Guide used: /feeds/2021-06-30/inventory and /pricing/2021-10-01/offers
            # I will follow the guide's intended logic.
            
            # Guide Step 1: Inventory
            # The URL in guide was /feeds/... which is async. 
            # I'll implement a direct sync version if possible or follow guide.
            # Guide: f"{self.SP_API_BASE}/feeds/2021-06-30/inventory"
            
            # Actually, Listings Items API is better for real-time.
            # I will implement using Listings Items API as it is synchronous-ish and better for this use case.
            
            listings_payload = {
                "productType": "PRODUCT",
                "requirements": "LISTING_OFFER_ONLY",
                "attributes": {
                    "condition_type": [{"value": "new_new", "marketplace_id": marketplace_id}],
                    "purchasable_offer": [{
                        "currency": "USD",
                        "our_price": [{"schedule": [{"value_with_tax": str(price)}]}],
                        "marketplace_id": marketplace_id
                    }],
                    "fulfillment_availability": [{
                        "fulfillment_channel_code": "DEFAULT",
                        "quantity": quantity
                    }]
                }
            }
            
            resp = await client.put(
                f"{self.SP_API_BASE}/listings/2021-08-01/items/{channel_context.get('seller_id')}/{sku}",
                json=listings_payload,
                headers=headers,
                params={"marketplaceIds": marketplace_id}
            )

            if resp.status_code not in (200, 202):
                return ListingResult(
                    success=False,
                    channel_name=self.channel_name,
                    error_message=f"Amazon listing creation failed: {resp.text}",
                )

        return ListingResult(
            success=True,
            external_listing_id=sku,  # Amazon uses SKU as the listing identifier
            channel_name=self.channel_name,
        )

    async def monitor_listing(self, channel_context: Dict, external_listing_id: str) -> ExternalListing:
        """Check current state of an Amazon listing by SKU."""
        token = channel_context["access_token"]
        seller_id = channel_context["seller_id"]
        marketplace_id = channel_context.get("marketplace_id", "ATVPDKIKX0D")

        headers = {
            "x-amz-access-token": token,
            "User-Agent": "Cephly/1.0"
        }

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.SP_API_BASE}/listings/2021-08-01/items/{seller_id}/{external_listing_id}",
                params={"marketplaceIds": marketplace_id, "includedData": "summaries,offers,fulfillmentAvailability"},
                headers=headers,
            )
            
            if resp.status_code != 200:
                 return ExternalListing(self.channel_name, external_listing_id, "", "", "Unknown", Decimal(0), 0, "unknown", datetime.utcnow())

            data = resp.json()
            # Parse response
            # Note: Complex response structure

        return ExternalListing(
            channel_name=self.channel_name,
            external_listing_id=external_listing_id,
            platform_product_id="",
            platform_variant_id="",
            title=data.get("summaries", [{}])[0].get("itemName", ""),
            listed_price=Decimal("0"), # Extract from offers
            stock_allocated=0, # Extract from fulfillmentAvailability
            status="active",
            created_at=datetime.utcnow(),
        )

    async def cancel_listing(self, channel_context: Dict, external_listing_id: str) -> bool:
        """Remove an Amazon listing by deleting the item."""
        token = channel_context["access_token"]
        seller_id = channel_context["seller_id"]
        marketplace_id = channel_context.get("marketplace_id", "ATVPDKIKX0D")

        headers = {
            "x-amz-access-token": token,
            "User-Agent": "Cephly/1.0"
        }

        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self.SP_API_BASE}/listings/2021-08-01/items/{seller_id}/{external_listing_id}",
                params={"marketplaceIds": marketplace_id},
                headers=headers,
            )

        return resp.status_code == 200

    async def sync_sales(self, channel_context: Dict, since: datetime) -> List[SyncedSale]:
        """Pull orders from Amazon since a given timestamp."""
        token = channel_context["access_token"]
        marketplace_id = channel_context.get("marketplace_id", "ATVPDKIKX0D")
        sales = []
        
        headers = {
            "x-amz-access-token": token,
            "User-Agent": "Cephly/1.0"
        }

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.SP_API_BASE}/orders/v0/orders",
                params={
                    "CreatedAfter": since.isoformat(),
                    "MarketplaceIds": marketplace_id
                },
                headers=headers,
            )
            data = resp.json()

            for order in data.get("payload", {}).get("Orders", []):
                # Need to fetch order items for each order to get SKU context
                # This is N+1, but required for Amazon Orders API
                order_id = order.get("AmazonOrderId")
                
                items_resp = await client.get(
                     f"{self.SP_API_BASE}/orders/v0/orders/{order_id}/orderItems",
                     headers=headers
                )
                items_data = items_resp.json()
                
                for item in items_data.get("payload", {}).get("OrderItems", []):
                    sales.append(SyncedSale(
                        external_listing_id=item.get("SellerSKU", ""),
                        channel_name=self.channel_name,
                        units_sold=int(item.get("QuantityOrdered", 1)),
                        revenue=Decimal(item.get("ItemPrice", {}).get("Amount", "0")),
                        sold_at=datetime.fromisoformat(order["PurchaseDate"]),
                        buyer_email=order.get("BuyerEmail"), # PII Restricted usually
                    ))

        return sales
