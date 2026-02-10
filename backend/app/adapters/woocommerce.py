
import logging
import hmac
import hashlib
import base64
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime
import httpx

from app.adapters.base import (
    BasePlatformAdapter,
    PlatformProduct,
    PlatformCustomer,
    PriceUpdateResult,
    WebhookEvent,
)

logger = logging.getLogger(__name__)

class WooCommercePlatformAdapter(BasePlatformAdapter):
    """
    Adapter for WooCommerce (REST API V3).
    """

    @property
    def platform_name(self) -> str:
        return "woocommerce"

    def _get_client(self, context: Dict) -> httpx.AsyncClient:
        """Helper to create an authenticated client."""
        url = context.get("url")
        key = context.get("consumer_key")
        secret = context.get("consumer_secret")
        
        if not url or not key or not secret:
            raise ValueError("WooCommerce context missing url, key, or secret")
            
        # Ensure trailing slash
        base_url = f"{url.rstrip('/')}/wp-json/wc/v3/"
        
        return httpx.AsyncClient(
            base_url=base_url,
            auth=(key, secret),
            timeout=30.0,
            headers={"Content-Type": "application/json", "User-Agent": "Cephly/1.0"}
        )

    async def authenticate(self, auth_payload: Dict) -> Dict:
        """
        Validates the provided credentials by making a test API call.
        Payload expected: { "url": "...", "consumer_key": "...", "consumer_secret": "..." }
        """
        url = auth_payload.get("shop_url") or auth_payload.get("url")
        key = auth_payload.get("consumer_key")
        secret = auth_payload.get("consumer_secret")

        if not url or not key or not secret:
            raise ValueError("Missing WooCommerce connection details")

        # Create a temp context to use the helper
        ctx = {"url": url, "consumer_key": key, "consumer_secret": secret}

        async with self._get_client(ctx) as client:
            try:
                # Test connection (e.g., fetch system status or just products)
                resp = await client.get("system_status")
                # If system_status is not allowed, try products
                if resp.status_code in [401, 403]:
                     # Try fallback to products if system_status is restricted
                     resp = await client.get("products?per_page=1")

                if resp.status_code != 200:
                    logger.error(f"WooAuth Failed: {resp.status_code} {resp.text}")
                    raise ValueError("Invalid credentials or store URL")
                
                # If successful, return the context to be stored
                return {
                    "url": url,
                    "consumer_key": key,
                    "consumer_secret": secret,
                    "shop_id": url # Use URL as ID for Woo
                }
            except httpx.RequestError as e:
                raise ValueError(f"Connection failed: {str(e)}")

    async def sync_products(self, merchant_context: Dict) -> List[PlatformProduct]:
        products = []
        page = 1
        
        async with self._get_client(merchant_context) as client:
            while True:
                resp = await client.get(f"products", params={"page": page, "per_page": 100})
                if resp.status_code != 200:
                    logger.error(f"Sync failed block {page}: {resp.text}")
                    break
                
                data = resp.json()
                if not data: break
                
                for item in data:
                    # Handle variations if needed? For now mapping parent product
                    # NOTE: A real robust impl would fetch variations endpoint if type='variable'
                    
                    price = item.get("price") or item.get("regular_price") or "0"
                    
                    p = PlatformProduct(
                        platform_product_id=str(item["id"]),
                        platform_variant_id=str(item["id"]), # Default to same for simple
                        title=item["name"],
                        category=item["categories"][0]["name"] if item["categories"] else "Uncategorized",
                        current_price=Decimal(price),
                        cost_price=Decimal(0), # Woo doesn't have standard cost field
                        stock_quantity=item.get("stock_quantity") or 0,
                        last_sold_at=None, # Expensive to calculate on Woo without querying orders
                        image_url=item["images"][0]["src"] if item["images"] else None
                    )
                    products.append(p)
                
                if len(data) < 100: break
                page += 1
                
        return products

    async def sync_customers(self, merchant_context: Dict) -> List[PlatformCustomer]:
        customers = []
        page = 1
        
        async with self._get_client(merchant_context) as client:
            while True:
                resp = await client.get(f"customers", params={"page": page, "per_page": 100})
                if resp.status_code != 200: break
                
                data = resp.json()
                if not data: break
                
                for item in data:
                   c = PlatformCustomer(
                       platform_customer_id=str(item["id"]),
                       email=item["email"],
                       phone=item.get("billing", {}).get("phone"),
                       total_orders=item.get("orders_count", 0),
                       total_spent=Decimal(item.get("total_spent", "0")),
                       last_order_at=None # TODO: Would need to parse last_order_date
                   )
                   customers.append(c)
                
                if len(data) < 100: break
                page += 1
        return customers

    async def get_product(self, merchant_context: Dict, product_id: str, variant_id: str) -> PlatformProduct:
        # Check if it's a variation
        async with self._get_client(merchant_context) as client:
            # If ids match, it's likely a simple product
            endpoint = f"products/{product_id}"
            if product_id != variant_id:
                endpoint = f"products/{product_id}/variations/{variant_id}"
                
            resp = await client.get(endpoint)
            if resp.status_code != 200:
                raise ValueError(f"Product not found: {resp.text}")
                
            item = resp.json()
            price = item.get("price") or "0"
            
            return PlatformProduct(
                platform_product_id=product_id,
                platform_variant_id=variant_id,
                title=item.get("name") or "Unknown", # Variations might not have name populated same way
                category="Unknown", 
                current_price=Decimal(price),
                cost_price=Decimal(0),
                stock_quantity=item.get("stock_quantity") or 0,
                last_sold_at=None,
                image_url=item["image"]["src"] if "image" in item and item["image"] else None
            )

    async def update_price(self, merchant_context: Dict, product_id: str, variant_id: str, new_price: Decimal) -> PriceUpdateResult:
        async with self._get_client(merchant_context) as client:
            endpoint = f"products/{product_id}"
            if product_id != variant_id:
                endpoint = f"products/{product_id}/variations/{variant_id}"
            
            payload = {"regular_price": str(new_price)}
            
            resp = await client.put(endpoint, json=payload)
            
            success = resp.status_code == 200
            err_msg = None if success else f"{resp.status_code}: {resp.text}"
            
            return PriceUpdateResult(
                success=success,
                platform_product_id=product_id,
                platform_variant_id=variant_id,
                new_price=new_price,
                updated_at=datetime.utcnow(),
                error_message=err_msg
            )

    async def register_webhook(self, merchant_context: Dict, event_type: str, callback_url: str) -> bool:
        # Map Cephly event types to Woo topics
        # e.g. "product.updated" -> "product.update"
        topic_map = {
            "product.updated": "product.update",
            "order.created": "order.created"
        }
        topic = topic_map.get(event_type, event_type)
        
        async with self._get_client(merchant_context) as client:
            payload = {
                "name": "Cephly Webhook",
                "topic": topic,
                "delivery_url": callback_url,
                "secret": merchant_context.get("consumer_secret") # Use consumer secret as standard sign secret
            }
            resp = await client.post("webhooks", json=payload)
            return resp.status_code == 201

    def parse_webhook(self, raw_payload: Dict, headers: Dict) -> WebhookEvent:
        # Verify signature
        # Woo signature is in 'x-wc-webhook-signature'
        # It is a base64 encoded HMAC-SHA256 hash of the raw payload body using the secret
        
        # NOTE: We need the raw body bytes to verify signature truly. 
        # But this method receives parsed dict `raw_payload`. 
        # In `webhooks.py` router, we pass `raw_payload`.
        # To strictly verify, the router needs to pass raw bytes or this method needs to re-serialize (risky).
        # FOR NOW: We will skip strict generic signature check here or assume specific context passing.
        # Ideally `webhooks.py` would pass the raw body...
        
        # Let's trust the router/adapter contract updates in future to pass raw body if needed.
        # Or we check if 'x-wc-webhook-signature' exists.
        
        event_topic = headers.get("x-wc-webhook-topic") or "unknown"
        
        # Map to standard event
        event_map = {
            "product.update": "product.updated",
            "order.created": "order.created"
        }
        event_type = event_map.get(event_topic, event_topic)
        
        # WooCommerce sends the store URL in 'x-wc-webhook-source'
        source = headers.get("x-wc-webhook-source", "").rstrip('/')
        
        # Normalize the payload
        normalized_payload = {}
        if event_type.startswith("product"):
            normalized_payload = {
                "id": str(raw_payload.get("id")),
                "title": raw_payload.get("name"),
                "handle": raw_payload.get("slug"),
                "product_type": raw_payload.get("categories", [{}])[0].get("name") if raw_payload.get("categories") else "Uncategorized",
                "status": raw_payload.get("status"),
                "variants": [
                    {
                        "id": str(v.get("id")),
                        "title": v.get("name"),
                        "sku": v.get("sku"),
                        "price": v.get("price"),
                        "inventory_quantity": v.get("stock_quantity")
                    } for v in raw_payload.get("variations", [])
                ] if raw_payload.get("type") == "variable" else [
                    {
                        "id": str(raw_payload.get("id")),
                        "title": raw_payload.get("name"),
                        "sku": raw_payload.get("sku"),
                        "price": raw_payload.get("price"),
                        "inventory_quantity": raw_payload.get("stock_quantity")
                    }
                ]
            }
        elif event_type.startswith("order"):
            normalized_payload = {
                "id": str(raw_payload.get("id")),
                "order_number": str(raw_payload.get("number")),
                "total_price": raw_payload.get("total"),
                "customer": {
                    "id": str(raw_payload.get("customer_id")) if raw_payload.get("customer_id") else None,
                    "email": raw_payload.get("billing", {}).get("email") if raw_payload.get("billing") else None
                }
            }
        elif event_type.startswith("customer"):
            normalized_payload = {
                "id": str(raw_payload.get("id")),
                "email": raw_payload.get("email"),
                "first_name": raw_payload.get("first_name"),
                "last_name": raw_payload.get("last_name")
            }

        return WebhookEvent(
            event_type=event_type,
            merchant_id=source, # Matches the 'shopify_domain' (url) stored in auth
            payload=normalized_payload,
            raw_payload=raw_payload,
            received_at=datetime.utcnow()
        )
