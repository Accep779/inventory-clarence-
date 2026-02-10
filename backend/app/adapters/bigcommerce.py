
import logging
import httpx
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime

from app.adapters.base import (
    BasePlatformAdapter,
    PlatformProduct,
    PlatformCustomer,
    PriceUpdateResult,
    WebhookEvent,
)
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class BigCommercePlatformAdapter(BasePlatformAdapter):
    """
    Adapter for BigCommerce (V3 API).
    """

    @property
    def platform_name(self) -> str:
        return "bigcommerce"

    def _get_client(self, context: Dict) -> httpx.AsyncClient:
        store_hash = context.get("store_hash")
        token = context.get("access_token")
        
        if not store_hash or not token:
            raise ValueError("BigCommerce context missing store_hash or access_token")
            
        base_url = f"https://api.bigcommerce.com/stores/{store_hash}/v3/"
        
        return httpx.AsyncClient(
            base_url=base_url,
            headers={
                "X-Auth-Token": token,
                "Content-Type": "application/json",
                "User-Agent": "Cephly/1.0"
            },
            timeout=30.0
        )

    async def authenticate(self, auth_payload: Dict) -> Dict:
        """
        Exchange OAuth code for access token.
        Payload expected: { "code": "...", "context": "...", "redirect_uri": "..." }
        """
        code = auth_payload.get("code")
        context = auth_payload.get("context") # stores/{hash}
        redirect_uri = auth_payload.get("redirect_uri")
        
        if not code or not context:
            raise ValueError("Missing code or context")

        # helper to extract hash from "stores/xyz"
        store_hash = context.split('/')[-1]

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://login.bigcommerce.com/oauth2/token",
                json={
                    "client_id": settings.BIGCOMMERCE_CLIENT_ID or "placeholder_id",
                    "client_secret": settings.BIGCOMMERCE_CLIENT_SECRET or "placeholder_secret",
                    "code": code,
                    "context": context,
                    "scope": auth_payload.get("scope", ""),
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri
                }
            )
            
            if resp.status_code != 200:
                logger.error(f"BigC Auth Failed: {resp.text}")
                raise ValueError("Failed to exchange token")
            
            data = resp.json()
            # Response: { access_token, scope, user: {id, username, email}, context, ... }
            
            return {
                "access_token": data["access_token"],
                "store_hash": store_hash,
                "shop_id": store_hash, # Use hash as ID
                "scope": data.get("scope"),
                "context": data.get("context")
            }

    async def sync_products(self, merchant_context: Dict) -> List[PlatformProduct]:
        products = []
        page = 1
        
        async with self._get_client(merchant_context) as client:
            while True:
                resp = await client.get("catalog/products", params={"page": page, "limit": 250, "include": "images"})
                if resp.status_code != 200:
                    break
                
                payload = resp.json()
                data = payload.get("data", [])
                if not data: break
                
                for item in data:
                    products.append(PlatformProduct(
                        platform_product_id=str(item["id"]),
                        platform_variant_id=str(item["id"]), # Simple product assumption for now
                        title=item["name"],
                        category="Uncategorized", # Categories are IDs in BigC, need mapping
                        current_price=Decimal(str(item["price"])),
                        cost_price=Decimal(str(item.get("cost_price", 0))),
                        stock_quantity=item.get("inventory_level", 0),
                        last_sold_at=None,
                        image_url=item["images"][0]["url_standard"] if item.get("images") else None
                    ))
                
                meta = payload.get("meta", {}).get("pagination", {})
                if page >= meta.get("total_pages", 0):
                    break
                page += 1
                
        return products

    async def sync_customers(self, merchant_context: Dict) -> List[PlatformCustomer]:
        customers = []
        page = 1
        
        async with self._get_client(merchant_context) as client:
            while True:
                resp = await client.get("customers", params={"page": page, "limit": 250})
                if resp.status_code != 200: break # BigC V3 Customers API is separate but usually v3/customers
                
                payload = resp.json()
                data = payload.get("data", [])
                if not data: break
                
                for item in data:
                    customers.append(PlatformCustomer(
                        platform_customer_id=str(item["id"]),
                        email=item["email"],
                        phone=item.get("phone"),
                        total_orders=0, # Need to query orders separately
                        total_spent=Decimal("0.00"), # Need to query orders
                        last_order_at=None
                    ))
                
                meta = payload.get("meta", {}).get("pagination", {})
                if page >= meta.get("total_pages", 0):
                    break
                page += 1
        return customers

    async def get_product(self, merchant_context: Dict, product_id: str, variant_id: str) -> PlatformProduct:
        async with self._get_client(merchant_context) as client:
            resp = await client.get(f"catalog/products/{product_id}", params={"include": "images"})
            if resp.status_code != 200:
                raise ValueError("Product not found")
            
            data = resp.json().get("data")
            return PlatformProduct(
                platform_product_id=str(data["id"]),
                platform_variant_id=str(data["id"]),
                title=data["name"],
                category="Uncategorized",
                current_price=Decimal(str(data["price"])),
                cost_price=Decimal(str(data.get("cost_price", 0))),
                stock_quantity=data.get("inventory_level", 0),
                last_sold_at=None,
                image_url=data["images"][0]["url_standard"] if data.get("images") else None
            )

    async def update_price(self, merchant_context: Dict, product_id: str, variant_id: str, new_price: Decimal) -> PriceUpdateResult:
        async with self._get_client(merchant_context) as client:
            payload = {"price": float(new_price)}
            resp = await client.put(f"catalog/products/{product_id}", json=payload)
            
            success = resp.status_code == 200
            error = None if success else resp.text
            
            return PriceUpdateResult(
                success=success,
                platform_product_id=product_id,
                platform_variant_id=variant_id,
                new_price=new_price,
                updated_at=datetime.utcnow(),
                error_message=error
            )

    async def register_webhook(self, merchant_context: Dict, event_type: str, callback_url: str) -> bool:
        # Map events
        # store/order/created
        # store/product/updated
        scope_map = {
            "product.updated": "store/product/updated",
            "order.created": "store/order/created"
        }
        scope = scope_map.get(event_type)
        if not scope: return False
        
        async with self._get_client(merchant_context) as client:
            payload = {
                "scope": scope,
                "destination": callback_url,
                "is_active": True
            }
            resp = await client.post("hooks", json=payload)
            return resp.status_code in [200, 201]

    def parse_webhook(self, raw_payload: Dict, headers: Dict) -> WebhookEvent:
        # BigCommerce payload structure:
        # { scope: "store/product/updated", data: { type: "product", id: 123 }, ... }
        
        scope = raw_payload.get("scope", "")
        
        event_map = {
            "store/product/updated": "product.updated",
            "store/order/created": "order.created"
        }
        event_type = event_map.get(scope, "unknown")
        
        # Normalize the payload
        normalized_payload = {}
        data = raw_payload.get("data", {})
        if event_type.startswith("product"):
            # NOTE: BigCommerce webhooks only send IDs, usually need to fetch details.
            # But we normalize the basic payload structure.
            normalized_payload = {
                "id": str(data.get("id")),
                "title": None, # Needs fetch
                "variants": [
                    {
                        "id": str(data.get("id")),
                        "price": None,
                        "inventory_quantity": None
                    }
                ]
            }
        elif event_type.startswith("order"):
            normalized_payload = {
                "id": str(data.get("id")),
                "order_number": str(data.get("id")), # BigC order ID is number
                "total_price": None, # Needs fetch
                "customer": {
                    "id": None,
                    "email": None
                }
            }

        # BigCommerce identifies the store in the 'producer' field (e.g., "stores/xyz")
        producer = raw_payload.get("producer", "")
        store_hash = producer.split('/')[-1] if '/' in producer else "unknown"

        return WebhookEvent(
            event_type=event_type,
            merchant_id=store_hash, 
            payload=normalized_payload,
            raw_payload=raw_payload,
            received_at=datetime.utcnow()
        )
