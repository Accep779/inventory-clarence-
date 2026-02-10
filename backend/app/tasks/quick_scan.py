"""
Quick Scan Task - Real-Time Dead Stock Discovery for Onboarding.

Scans first 50 products with live updates via Redis pub/sub.
Creates dramatic reveal experience during merchant onboarding.

LOGIC EXTRACTED FROM: ObserverAgent velocity + classification
"""

import asyncio
import time
from uuid import uuid4
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional

import httpx
from sqlalchemy import select, func

# NOTE: Celery removed. Use Temporal activities for production tasks.
from app.config import get_settings
from app.database import async_session_maker
from app.models import Merchant, Product, OrderItem, InboxItem
from app.services.scan_broadcaster import get_broadcaster
from app.orchestration import background_task, registry

settings = get_settings()

# Scan settings
QUICK_SCAN_LIMIT = 50
DELAY_BETWEEN_PRODUCTS = 0.5  # Dramatic reveal timing


@background_task(name="start_quick_scan", queue="scan")
async def start_quick_scan(merchant_id: str, session_id: str):
    """
    Start quick scan for onboarding.

    Fetches first 50 products from Shopify, analyzes each,
    and broadcasts dead stock finds in real-time.

    Args:
        merchant_id: The merchant being scanned
        session_id: Unique session for pub/sub channel
    """
    await _quick_scan_async(merchant_id, session_id)


# Register task
registry.register_background_task(start_quick_scan)


async def _quick_scan_async(merchant_id: str, session_id: str):
    """Async implementation of quick scan."""
    broadcaster = get_broadcaster()
    
    try:
        async with async_session_maker() as session:
            # Get merchant
            result = await session.execute(
                select(Merchant).where(Merchant.id == merchant_id)
            )
            merchant = result.scalar_one_or_none()
            
            if not merchant:
                broadcaster.publish_error(session_id, "Merchant not found")
                return
            
            # Fetch products from Shopify (first 50 only)
            products = await _fetch_shopify_products(merchant, limit=QUICK_SCAN_LIMIT)
            
            if not products:
                broadcaster.publish_error(session_id, "No products found in store")
                return
            
            total_stuck_value = 0.0
            dead_stock_count = 0
            dead_stock_products = []
            
            from app.agents.observer import ObserverAgent
            from app.agents.strategy import StrategyAgent
            
            observer = ObserverAgent(merchant_id)
            strategy_agent = StrategyAgent(merchant_id)
            
            for i, product_data in enumerate(products):
                # Analyze using the new Agent (Reasoning + Memory)
                analysis = await observer.observe_product(
                    product_data, 
                    session
                )
                
                # Broadcast progress
                broadcaster.publish_scan_progress(
                    session_id,
                    products_scanned=i + 1,
                    total_products=len(products)
                )
                
                if analysis["is_dead_stock"]:
                    dead_stock_count += 1
                    stuck_value = analysis["stuck_value"]
                    total_stuck_value += stuck_value
                    
                    # Build product info for frontend
                    product_info = {
                        "title": product_data.get("title", "Unknown"),
                        "price": analysis["price"],
                        "inventory": analysis["inventory"],
                        "stuck_value": stuck_value,
                        "days_since_last_sale": analysis["days_since_last_sale"],
                        "velocity_score": analysis["velocity_score"],
                        "severity": analysis["severity"],
                        "image_url": _get_product_image(product_data),
                        "reasoning": analysis["reasoning"] # NEW: Pass reasoning to UI
                    }
                    
                    dead_stock_products.append(product_info)
                    
                    # Create a real proposal via StrategyAgent for the top finds
                    if dead_stock_count <= 3:
                        try:
                            # We use the product data from Shopify to find or create DB product
                            db_product_result = await session.execute(
                                select(Product).where(Product.shopify_product_id == product_data['id'])
                            )
                            db_p = db_product_result.scalar_one_or_none()
                            if db_p:
                                await strategy_agent.plan_clearance(db_p.id)
                        except Exception as e:
                            print(f"⚠️ Failed to generate strategy: {e}")
                    
                    # Broadcast dead stock find
                    broadcaster.publish_dead_stock_found(
                        session_id,
                        product=product_info,
                        running_total={
                            "dead_stock_count": dead_stock_count,
                            "total_stuck_value": round(total_stuck_value, 2),
                            "products_scanned": i + 1,
                            "total_products": len(products)
                        }
                    )
                    
                    # Dramatic delay for visual effect
                    time.sleep(DELAY_BETWEEN_PRODUCTS)
            
            # Quick scan complete
            broadcaster.publish_quick_scan_complete(
                session_id,
                summary={
                    "dead_stock_count": dead_stock_count,
                    "total_stuck_value": round(total_stuck_value, 2),
                    "products_scanned": len(products),
                    "remaining_products": await _get_remaining_products_count(merchant) - len(products)
                }
            )
            
            await session.commit()
            
            print(f"✅ Quick scan complete: {dead_stock_count} dead stock, ${total_stuck_value:,.2f} stuck")
    
    except Exception as e:
        print(f"❌ Quick scan error: {e}")
        broadcaster.publish_error(session_id, str(e))


async def _fetch_shopify_products(merchant: Merchant, limit: int = 50) -> List[Dict]:
    """Fetch products directly from Shopify API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://{merchant.shopify_domain}/admin/api/{settings.SHOPIFY_API_VERSION}/products.json",
            headers={"X-Shopify-Access-Token": merchant.access_token},
            params={"limit": limit, "status": "active"}
        )
        
        if response.status_code != 200:
            print(f"❌ Shopify API error: {response.status_code}")
            return []
        
        return response.json().get("products", [])


async def _analyze_product(
    product_data: Dict, 
    merchant_id: str, 
    session
) -> Dict[str, Any]:
    """
    Analyze a single product for dead stock status.
    LOGIC FROM: ObserverAgent._calculate_velocity_score + _classify_dead_stock
    """
    shopify_product_id = product_data.get("id")
    variants = product_data.get("variants", [])
    
    # Get price and inventory
    price = float(variants[0].get("price", 0)) if variants else 0
    inventory = sum(v.get("inventory_quantity", 0) for v in variants)
    
    # Check if we have this product in DB already (for sales data)
    result = await session.execute(
        select(Product).where(
            Product.shopify_product_id == shopify_product_id,
            Product.merchant_id == merchant_id
        )
    )
    db_product = result.scalar_one_or_none()
    
    # Calculate days since last sale
    if db_product and db_product.last_sale_date:
        days_since_sale = (datetime.utcnow() - db_product.last_sale_date).days
    else:
        # No sales data - estimate based on created date
        created_at_str = product_data.get("created_at", "")
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                days_since_sale = min((datetime.utcnow() - created_at.replace(tzinfo=None)).days, 365)
            except:
                days_since_sale = 180  # Default assumption
        else:
            days_since_sale = 180
    
    # Get sales metrics from DB if available
    units_30d = db_product.units_sold_30d if db_product else 0
    units_60d = db_product.units_sold_60d if db_product else 0
    
    # Calculate velocity score (simplified from Observer)
    avg_inventory = max(inventory, 1)
    turnover_rate = (units_30d / avg_inventory) * 12 if avg_inventory > 0 else 0
    turnover_normalized = min(turnover_rate / 12, 1.0) * 100
    
    # Recency score
    recency_normalized = max(0, (180 - days_since_sale) / 180) * 100
    
    # Weighted velocity score
    velocity_score = (turnover_normalized * 0.6) + (recency_normalized * 0.4)
    
    # Classify dead stock
    is_dead_stock = False
    severity = None
    
    if velocity_score < 20 and turnover_rate < 2 and days_since_sale >= 90:
        is_dead_stock = True
        severity = "critical"
    elif velocity_score < 35 and turnover_rate < 4:
        is_dead_stock = True
        severity = "high"
    elif velocity_score < 50 and turnover_rate < 6:
        is_dead_stock = True
        severity = "moderate"
    elif velocity_score < 65:
        is_dead_stock = True
        severity = "low"
    
    # Calculate stuck value
    stuck_value = price * inventory if is_dead_stock else 0
    
    return {
        "is_dead_stock": is_dead_stock,
        "severity": severity,
        "velocity_score": round(velocity_score, 1),
        "days_since_last_sale": days_since_sale,
        "turnover_rate": round(turnover_rate, 2),
        "price": price,
        "inventory": inventory,
        "stuck_value": round(stuck_value, 2)
    }


def _get_product_image(product_data: Dict) -> Optional[str]:
    """Extract first product image URL."""
    images = product_data.get("images", [])
    if images:
        return images[0].get("src")
    return None


async def _get_remaining_products_count(merchant: Merchant) -> int:
    """Get total product count from Shopify."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://{merchant.shopify_domain}/admin/api/{settings.SHOPIFY_API_VERSION}/products/count.json",
            headers={"X-Shopify-Access-Token": merchant.access_token},
            params={"status": "active"}
        )
        if response.status_code == 200:
            return response.json().get("count", 0)
        return 0


async def _generate_quick_proposals(
    merchant_id: str,
    dead_stock_products: List[Dict],
    session
):
    """
    Generate 2-3 quick proposals from top dead stock.
    Populates inbox before merchant reaches dashboard.
    """
    for product in dead_stock_products:
        # Map severity to action
        action_map = {
            "critical": "aggressive_liquidation",
            "high": "flash_sale",
            "moderate": "progressive_discount",
            "low": "bundle_promotion"
        }
        recommended_action = action_map.get(product["severity"], "flash_sale")
        
        proposal = InboxItem(
            merchant_id=merchant_id,
            type="dead_stock_alert",
            status="pending",
            agent_type="quick_scan",
            confidence=Decimal("90.00"),
            proposal_data={
                "product_title": product["title"],
                "severity": product["severity"],
                "velocity_score": product["velocity_score"],
                "days_since_last_sale": product["days_since_last_sale"],
                "current_inventory": product["inventory"],
                "estimated_value_locked": product["stuck_value"],
                "recommended_action": recommended_action,
                "message": f"Found during onboarding scan. {product['inventory']} units valued at ${product['stuck_value']:,.2f} need attention.",
                "source": "quick_scan"
            }
        )
        session.add(proposal)
    
    print(f"📝 Generated {len(dead_stock_products)} quick proposals")
