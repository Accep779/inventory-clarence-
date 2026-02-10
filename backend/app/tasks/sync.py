"""
Data Sync Tasks.

Background tasks for syncing data from Shopify after OAuth.

MIGRATION NOTE: These tasks are being migrated from Celery to Temporal.
For now, they run as direct async functions. Future: Move to Temporal activities.
"""

import asyncio
import httpx
from datetime import datetime

from app.config import get_settings
from app.database import async_session_maker
from app.models import Merchant, Product, ProductVariant, Customer, Order, OrderItem
from sqlalchemy import select, func
from app.adapters.registry import AdapterRegistry
from app.orchestration import background_task, registry

settings = get_settings()


# TODO: Migrate to Temporal activity for better durability
@background_task(name="initial_sync", queue="sync")
async def initial_sync(merchant_id: str):
    """
    Trigger initial data sync after OAuth.

    Syncs:
    - All products
    - All customers
    - Recent orders (last 90 days)
    """
    await _initial_sync_async(merchant_id)


# Register for discovery
registry.register_background_task(initial_sync)


async def _initial_sync_async(merchant_id: str):
    """Async implementation of initial sync."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Merchant).where(Merchant.id == merchant_id)
        )
        merchant = result.scalar_one_or_none()
        
        if not merchant:
            print(f"❌ Merchant {merchant_id} not found")
            return
        
        # [Day 0 Reliability] Update status to prevent race conditions
        merchant.sync_status = "syncing"
        await session.commit()
        
        print(f"🔄 Starting initial sync for {merchant.store_name}")
        
        try:
            # Resolve Adapter for the merchant's platform
            adapter = AdapterRegistry.get_adapter(merchant.platform)
            merchant_context = merchant.platform_context or {}

            # Sync products via adapter
            await sync_products(merchant, adapter, merchant_context, session)
            
            # Sync customers via adapter
            await sync_customers(merchant, adapter, merchant_context, session)
            
            # Sync orders via adapter (assuming Shopify specifics for now until adapter has generic order sync)
            # NOTE: For now, we keep sync_orders as is if adapter doesn't support it yet, 
            # but ideally we'd add it to the base adapter.
            await sync_orders(merchant, session)
            
            # [FINTECH FIX]: Aggregation Engine
            # Calculate actual sales and refund counts for the last 30 days
            await refresh_velocity_metrics(merchant_id, session)

            # [ENGINE #7]: Attribution & ROI Tracking
            from app.services.attribution import AttributionService
            attr_service = AttributionService(merchant_id)
            await attr_service.sync_ledger()
            
            # [THE COGNITIVE LAYER UPGRADE]
            # Trigger DNA Analysis (extract brand tone & financial benchmarks)
            from app.services.dna import DNAService
            dna_service = DNAService(merchant_id)
            await dna_service.analyze_store_dna()
            
            # [ENGINE #5]: Proactive Scan Engine
            # Wake up agents to look at the fresh data
            from app.services.proactive_scan import ProactiveScanService
            scanner = ProactiveScanService(merchant_id)
            await scanner.scan_for_triggers()
            
            # [Day 0 Reliability] Mark complete
            merchant.sync_status = "completed"
            await session.commit()
            print(f"✅ Initial sync complete for {merchant.store_name}")
            
        except Exception as e:
            print(f"❌ Initial sync failed for {merchant.store_name}: {e}")
            merchant.sync_status = "failed"
            await session.commit()



async def _fetch_shopify_resource(client, url: str, params: dict, access_token: str, merchant_id: Optional[str] = None, db: Optional[Any] = None):
    """
    Generator that yields pages of results from Shopify.
    Handles pagination and Rate Limits (429).
    """
    from app.integrations.circuit_breaker import get_shopify_circuit_breaker, CircuitBreakerOpenError
    
    next_url = url
    current_params = params
    
    while next_url:
        # Rate Limit / Retry Loop
        while True:
            try:
                breaker = get_shopify_circuit_breaker()
                
                # Internal function to pass to breaker.call
                async def _get():
                    return await client.get(
                        next_url,
                        headers={"X-Shopify-Access-Token": access_token},
                        params=current_params,
                    )
                
                response = await breaker.call(_get, merchant_id=merchant_id, db=db)
                
                if response.status_code == 429:
                    # [RESILIENCE]: Rate Limit Handling
                    retry_after = float(response.headers.get("Retry-After", "5.0"))
                    print(f"⏳ Shopify Rate Limit. Sleeping {retry_after}s...")
                    await asyncio.sleep(retry_after)
                    continue
                    
                if response.status_code != 200:
                    print(f"❌ Failed to fetch {next_url}: {response.status_code}")
                    return
                
                break
            except CircuitBreakerOpenError as e:
                print(f"🛑 Shopify Circuit OPEN for {merchant_id}. Retrying in {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
                continue
            except Exception as e:
                print(f"❌ Unexpected error in Shopify fetch: {e}")
                return
            
        data = response.json()
        # Determine key (products, customers, orders)
        key = next(iter(data.keys()))
        items = data.get(key, [])
        
        if not items:
            break
            
        yield items
        
        # Check for pagination
        link_header = response.headers.get("Link", "")
        next_url = None
        current_params = {} # Params are in the link URL
        
        if 'rel="next"' in link_header:
            for link in link_header.split(","):
                if 'rel="next"' in link:
                    next_url = link.split(";")[0].strip("<> ")
                    break

async def sync_products(merchant: Merchant, adapter, context: dict, session):
    """Sync all products using the platform adapter."""
    print(f"📦 Syncing products for {merchant.store_name} via {merchant.platform}...")
    
    total_synced = 0
    try:
        products = await adapter.sync_products(context)
        for product_data in products:
            await _save_product(product_data, merchant.id, session)
        
        await session.commit()
        total_synced = len(products)
        print(f"   Synced {total_synced} products")
    except Exception as e:
        print(f"❌ Product sync failed: {e}")

    print(f"📦 Completed product sync: {total_synced} total.")

async def sync_customers(merchant: Merchant, adapter, context: dict, session):
    """Sync all customers using the platform adapter."""
    print(f"👥 Syncing customers for {merchant.store_name} via {merchant.platform}...")
    
    total_synced = 0
    try:
        customers = await adapter.sync_customers(context)
        for customer_data in customers:
            await _save_customer(customer_data, merchant.id, session)
            
        await session.commit()
        total_synced = len(customers)
        print(f"   Synced {total_synced} customers")
    except Exception as e:
        print(f"❌ Customer sync failed: {e}")
            
    print(f"👥 Completed customer sync: {total_synced} total.")

async def _save_product(p: Any, merchant_id: str, session):
    """
    Saves or updates a platform-normalized product.
    Handles PlatformProduct dataclass.
    """
    # Check if already exists (using platform_product_id)
    # NOTE: We still use 'shopify_product_id' column for mapping until next migration
    from app.models import Product, ProductVariant
    
    stmt = select(Product).where(
        Product.shopify_product_id == p.platform_product_id,
        Product.merchant_id == merchant_id
    )
    res = await session.execute(stmt)
    product = res.scalar_one_or_none()
    
    if not product:
        product = Product(
            shopify_product_id=p.platform_product_id,
            merchant_id=merchant_id,
            title=p.title,
            handle=p.title.lower().replace(" ", "-"), # Basic slug
            product_type=p.category,
            status="active",
            total_inventory=p.stock_quantity,
            variant_count=1
        )
        session.add(product)
        await session.flush()
    else:
        product.title = p.title
        product.total_inventory = p.stock_quantity
        product.product_type = p.category

    # Save variant
    var_stmt = select(ProductVariant).where(ProductVariant.shopify_variant_id == p.platform_variant_id)
    var_res = await session.execute(var_stmt)
    variant = var_res.scalar_one_or_none()
    
    if not variant:
        variant = ProductVariant(
            shopify_variant_id=p.platform_variant_id,
            product_id=product.id,
            title=p.title,
            price=float(p.current_price),
            inventory_quantity=p.stock_quantity
        )
        session.add(variant)
    else:
        variant.price = float(p.current_price)
        variant.inventory_quantity = p.stock_quantity

async def _save_customer(c: Any, merchant_id: str, session):
    """
    Saves or updates a platform-normalized customer.
    Handles PlatformCustomer dataclass.
    """
    from app.models import Customer
    stmt = select(Customer).where(
        Customer.shopify_customer_id == c.platform_customer_id,
        Customer.merchant_id == merchant_id
    )
    res = await session.execute(stmt)
    customer = res.scalar_one_or_none()
    
    if not customer:
        customer = Customer(
            shopify_customer_id=c.platform_customer_id,
            merchant_id=merchant_id,
            email=c.email,
            phone=c.phone,
            total_orders=c.total_orders,
            total_spent=c.total_spent,
            last_order_date=c.last_order_at
        )
        session.add(customer)
    else:
        customer.email = c.email
        customer.phone = c.phone
        customer.total_orders = c.total_orders
        customer.total_spent = c.total_spent
        customer.last_order_date = c.last_order_at


async def sync_orders(merchant: Merchant, session):
    """Sync recent orders from Shopify using memory-efficient streaming."""
    print(f"🛒 Syncing orders for {merchant.store_name}...")
    
    from datetime import timedelta
    since_date = (datetime.utcnow() - timedelta(days=90)).isoformat()
    
    total_synced = 0
    
    async with httpx.AsyncClient() as client:
        url = f"https://{merchant.shopify_domain}/admin/api/{settings.SHOPIFY_API_VERSION}/orders.json"
        params = {"limit": 250, "created_at_min": since_date, "status": "any"}
        
        async for batch in _fetch_shopify_resource(client, url, params, merchant.access_token, merchant_id=merchant.id, db=session):
            for order_data in batch:
                await _save_order(order_data, merchant.id, session)
            
            await session.commit()
            total_synced += len(batch)
            print(f"   Saved batch of {len(batch)} orders (Total: {total_synced})")
            
    print(f"🛒 Completed order sync: {total_synced} total.")



async def _save_order(order_data: dict, merchant_id: str, session):
    """Save an order and its line items."""
    shopify_order_id = order_data.get("id")
    
    # Check if already exists
    result = await session.execute(
        select(Order).where(Order.shopify_order_id == shopify_order_id)
    )
    if result.scalar_one_or_none():
        return  # Skip if already synced
    
    # Find customer
    customer_id = None
    customer_data = order_data.get("customer")
    if customer_data:
        customer_result = await session.execute(
            select(Customer).where(
                Customer.shopify_customer_id == customer_data.get("id"),
                Customer.merchant_id == merchant_id
            )
        )
        customer = customer_result.scalar_one_or_none()
        if customer:
            customer_id = customer.id
    
    order = Order(
        shopify_order_id=shopify_order_id,
        merchant_id=merchant_id,
        customer_id=customer_id,
        order_number=str(order_data.get("order_number", "")),
        total_price=order_data.get("total_price", 0),
        subtotal_price=order_data.get("subtotal_price", 0),
        total_tax=order_data.get("total_tax", 0),
        created_at=datetime.fromisoformat(
            order_data.get("created_at", datetime.utcnow().isoformat()).replace("Z", "+00:00")
        ),
    )
    session.add(order)
    await session.flush()
    
    # Save line items
    for item in order_data.get("line_items", []):
        # Find product
        product_result = await session.execute(
            select(Product).where(
                Product.shopify_product_id == item.get("product_id"),
                Product.merchant_id == merchant_id
            )
        )
        product = product_result.scalar_one_or_none()
        
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id if product else None,
            quantity=item.get("quantity", 1),
            price=item.get("price", 0),
        )
        session.add(order_item)
        
        # Update product last sale date
        if product:
            product.last_sale_date = order.created_at
async def refresh_velocity_metrics(merchant_id: str, session):
    """
    [FINTECH FIX]: Aggregation Engine.
    Refreshes units_sold_30d efficiently using bulk updates.
    """
    print(f"📊 [Aggregation] Refreshing velocity metrics for merchant {merchant_id}...")
    
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    
    # 1. Reset metrics for all products
    from sqlalchemy import update
    await session.execute(
        update(Product)
        .where(Product.merchant_id == merchant_id)
        .values(units_sold_30d=0, units_refunded_30d=0)
    )
    
    # 2. Calculate sales in one query
    stmt = (
        select(OrderItem.product_id, func.sum(OrderItem.quantity))
        .join(Order, Order.id == OrderItem.order_id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(
            Product.merchant_id == merchant_id,
            Order.created_at >= cutoff_date
        )
        .group_by(OrderItem.product_id)
    )
    
    result = await session.execute(stmt)
    sales_data = result.all()
    
    # 3. Bulk Update
    # SQLAlchemy async bulk update via mappings is complex, so we iterate the results (checking M items, where M << N products)
    # If M is large, we can batch this too.
    for product_id, quantity in sales_data:
        await session.execute(
            update(Product)
            .where(Product.id == product_id)
            .values(units_sold_30d=int(quantity))
        )
        
    await session.commit()
    print(f"✅ [Aggregation] Metrics refreshed for {len(sales_data)} active products.")
