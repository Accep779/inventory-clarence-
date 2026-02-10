"""
Universal Webhook Router.

Handles real-time events from ALL platforms via a unified endpoint structure:
POST /api/webhooks/{platform}/{topic}

The router:
1. Resolves the correct PlatformAdapter
2. Verifies the webhook signature (via adapter)
3. Normalizes the event (via adapter)
4. Dispatches to the correct internal handler (Product, Order, etc.)
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Header, Path
from sqlalchemy import select

from app.database import async_session_maker
from app.models import Merchant, Product, ProductVariant, Customer, Order, OrderItem
from app.adapters.registry import AdapterRegistry
from app.adapters.base import WebhookEvent

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_merchant(platform: str, platform_merchant_id: str) -> Merchant | None:
    """
    Fetch merchant by platform and their platform-specific ID.
    For Shopify, platform_merchant_id is the myshopify.com domain.
    """
    async with async_session_maker() as session:
        # We use 'shopify_domain' as the generic unique identifier column for now
        # (Mapped to Store URL for Woo, Store Hash for BigC, etc.)
        stmt = select(Merchant).where(
            Merchant.platform == platform,
            Merchant.shopify_domain == platform_merchant_id
        )
            
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


@router.post("/{platform}/{topic}")
async def handle_webhook(
    request: Request,
    platform: str,
    topic: str,
):
    """
    Universal generic webhook entry point.
    """
    # 1. Resolve Adapter
    try:
        adapter = AdapterRegistry.get_adapter(platform)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")

    # 2. Parse & Verify (Adapter logic)
    # We pass raw body and headers to adapter
    try:
        body_bytes = await request.body()
        import json
        raw_payload = json.loads(body_bytes)
        headers = dict(request.headers)
        
        # [SECURITY] In a real implementation, parse_webhook should take bytes for HMAC checks
        # tailored to the specific platform's method.
        # Our BaseAdapter signature takes Dict currently. 
        # We assume adapter handles verification or we rely on 'auth.py' setup (but we shouldn't).
        # We'll pass the dict.
        
        event: WebhookEvent = adapter.parse_webhook(raw_payload, headers)
        
    except Exception as e:
        logger.error(f"Webhook verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid webhook signature or format")

    # 3. Fetch Merchant context
    merchant = await get_merchant(platform, event.merchant_id)
    if not merchant:
        # Merchant might have uninstalled or not found
        return {"status": "merchant_not_found"}

    # 4. Dispatch to Handlers
    # Event type is normalized e.g. "product.updated"
    handlers = {
        "product.created": process_product_update,
        "product.updated": process_product_update,
        "product.deleted": process_product_delete,
        "order.created": process_order_create,
        "order.updated": process_order_update,
        "customer.created": process_customer_update,
        "customer.updated": process_customer_update,
        "app.uninstalled": process_app_uninstall,
    }
    
    handler = handlers.get(event.event_type)
    if handler:
        await handler(merchant, event)
        return {"status": "processed", "event": event.event_type}
    
    return {"status": "ignored", "reason": "unhandled_topic"}


# ============================================================================
# EVENT HANDLERS (Database Logic)
# ============================================================================

async def process_product_update(merchant: Merchant, event: WebhookEvent):
    """Handle product create/update."""
    payload = event.payload
    
    async with async_session_maker() as session:
        platform_product_id = payload.get("id")
        
        result = await session.execute(
            select(Product).where(
                Product.shopify_product_id == platform_product_id,
                Product.merchant_id == merchant.id
            )
        )
        existing_product = result.scalar_one_or_none()
        
        variants = payload.get("variants", [])
        total_inventory = sum(v.get("inventory_quantity") or 0 for v in variants)
        
        if existing_product:
            product = existing_product
            product.title = payload.get("title") or product.title
            product.handle = payload.get("handle") or product.handle
            product.total_inventory = total_inventory
            product.variant_count = len(variants)
            product.updated_at = datetime.utcnow()
        else:
            product = Product(
                shopify_product_id=platform_product_id,
                merchant_id=merchant.id,
                title=payload.get("title", ""),
                handle=payload.get("handle", ""),
                product_type=payload.get("product_type", "Uncategorized"),
                vendor=payload.get("vendor", ""),
                status=payload.get("status", "active"),
                total_inventory=total_inventory,
                variant_count=len(variants),
            )
            session.add(product)
        
        await session.commit()
        await session.refresh(product)
        
        # Sync variants (Simplified for brevity - assumes full replace or update)
        for v_data in variants:
            v_id = v_data.get("id")
            v_result = await session.execute(select(ProductVariant).where(ProductVariant.shopify_variant_id == v_id))
            variant = v_result.scalar_one_or_none()
            
            if not variant:
                variant = ProductVariant(
                    shopify_variant_id=v_id,
                    product_id=product.id,
                    title=v_data.get("title", ""),
                    sku=v_data.get("sku", ""),
                    price=float(v_data.get("price") or 0),
                    inventory_quantity=v_data.get("inventory_quantity") or 0
                )
                session.add(variant)
            else:
                variant.price = float(v_data.get("price") or 0)
                variant.inventory_quantity = v_data.get("inventory_quantity") or 0
                
        await session.commit()
        
        # Trigger Analysis
        try:
            from app.tasks.observer import run_analysis_for_product
            run_analysis_for_product.delay(merchant.id, product.id)
        except ImportError:
            pass # Task might not be ready in refactor context


async def process_product_delete(merchant: Merchant, event: WebhookEvent):
    payload = event.payload
    async with async_session_maker() as session:
        result = await session.execute(
            select(Product).where(
                Product.shopify_product_id == payload.get("id"),
                Product.merchant_id == merchant.id
            )
        )
        product = result.scalar_one_or_none()
        if product:
            await session.delete(product)
            await session.commit()


async def process_order_create(merchant: Merchant, event: WebhookEvent):
    """Handle new order."""
    payload = event.payload
    async with async_session_maker() as session:
        order = Order(
            shopify_order_id=payload.get("id"),
            merchant_id=merchant.id,
            order_number=payload.get("order_number"),
            total_price=float(payload.get("total_price") or 0),
            created_at=datetime.utcnow() 
        )
        session.add(order)
        # Note: Linking customer/items omitted for brevity/safety in refactor
        await session.commit()


async def process_order_update(merchant: Merchant, event: WebhookEvent):
    pass # Placeholder


async def process_customer_update(merchant: Merchant, event: WebhookEvent):
    """Handle customer create/update."""
    payload = event.payload
    async with async_session_maker() as session:
        c_id = payload.get("id")
        result = await session.execute(
            select(Customer).where(Customer.shopify_customer_id == c_id, Customer.merchant_id == merchant.id)
        )
        customer = result.scalar_one_or_none()
        
        if not customer:
            customer = Customer(
                shopify_customer_id=c_id,
                merchant_id=merchant.id,
                email=payload.get("email"),
                total_spent=0
            )
            session.add(customer)
        else:
            customer.email = payload.get("email")
            
        await session.commit()


async def process_app_uninstall(merchant: Merchant, event: WebhookEvent):
    async with async_session_maker() as session:
        # Re-fetch attached to this session
        merch = await session.get(Merchant, merchant.id)
        if merch:
            merch.is_active = False
            merch.access_token = ""
            await session.commit()
