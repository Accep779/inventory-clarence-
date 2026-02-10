# backend/app/activities/scan.py
import asyncio
import time
from typing import Dict, List, Optional
from temporalio import activity
from sqlalchemy import select

from app.database import async_session_maker
from app.models import Merchant, Product, InboxItem
from app.services.scan_broadcaster import get_broadcaster
from app.config import get_settings
import httpx
from datetime import datetime
from decimal import Decimal

settings = get_settings()

class ScanActivities:
    def __init__(self):
        pass

    @activity.defn
    async def quick_scan_product_batch(self, merchant_id: str, session_id: str, limit: int = 50) -> Dict:
        """
        Scans a batch of products (first 50) for the quick scan.
        Returns a summary of dead stock found.
        """
        broadcaster = get_broadcaster()
        
        async with async_session_maker() as session:
            # Get merchant
            result = await session.execute(
                select(Merchant).where(Merchant.id == merchant_id)
            )
            merchant = result.scalar_one_or_none()
            
            if not merchant:
                broadcaster.publish_error(session_id, "Merchant not found")
                return {"status": "failed", "error": "Merchant not found"}
            
            # Fetch products from Shopify
            products = await self._fetch_shopify_products(merchant, limit=limit)
            
            if not products:
                broadcaster.publish_error(session_id, "No products found in store")
                return {"status": "completed", "dead_stock_count": 0, "products_scanned": 0}
            
            total_stuck_value = 0.0
            dead_stock_count = 0
            dead_stock_products = []
            
            # Lazy import to avoid circular dep if any
            from app.agents.observer import ObserverAgent
            from app.agents.strategy import StrategyAgent
            
            observer = ObserverAgent(merchant_id)
            strategy_agent = StrategyAgent(merchant_id)
            
            for i, product_data in enumerate(products):
                # Heartbeat to keep activity alive during long processing
                activity.heartbeat(f"Scanning product {i+1}/{len(products)}")
                
                # Analyze using Agent
                analysis = await observer.observe_product(product_data, session)
                
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
                    
                    product_info = {
                        "title": product_data.get("title", "Unknown"),
                        "price": analysis["price"],
                        "inventory": analysis["inventory"],
                        "stuck_value": stuck_value,
                        "days_since_last_sale": analysis["days_since_last_sale"],
                        "velocity_score": analysis["velocity_score"],
                        "severity": analysis["severity"],
                        "image_url": self._get_product_image(product_data),
                        "reasoning": analysis["reasoning"]
                    }
                    
                    dead_stock_products.append(product_info)
                    
                    # Create Proposal for top finds
                    if dead_stock_count <= 3:
                        try:
                            db_product_result = await session.execute(
                                select(Product).where(Product.shopify_product_id == product_data['id'])
                            )
                            db_p = db_product_result.scalar_one_or_none()
                            if db_p:
                                await strategy_agent.plan_clearance(db_p.id)
                        except Exception as e:
                            print(f"⚠️ Failed to generate strategy: {e}")
                            
                    # Broadcast find
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
                    
                    # Artificial delay for drama
                    await asyncio.sleep(0.5)

            # Generate Inbox Items for top proposals (if not already handled by strategy agent above? logic in original task was slightly duplicated)
            # The original task had `_generate_quick_proposals` which wrote to InboxItem.
            # `strategy_agent.plan_clearance` also writes to InboxItem.
            # We will rely on strategy_agent.plan_clearance as it is the "proper" way.
            # If we need the manual fallback:
            if dead_stock_products and dead_stock_count > 0:
                 await self._generate_quick_proposals_fallback(merchant_id, dead_stock_products[:3], session)

            await session.commit()
            
            # Broadcast Complete
            broadcaster.publish_quick_scan_complete(
                session_id,
                summary={
                    "dead_stock_count": dead_stock_count,
                    "total_stuck_value": round(total_stuck_value, 2),
                    "products_scanned": len(products),
                    "remaining_products": await self._get_remaining_products_count(merchant) - len(products)
                }
            )
            
            return {
                "status": "success",
                "dead_stock_count": dead_stock_count,
                "total_stuck_value": total_stuck_value
            }

    async def _fetch_shopify_products(self, merchant: Merchant, limit: int = 50) -> List[Dict]:
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

    def _get_product_image(self, product_data: Dict) -> Optional[str]:
        images = product_data.get("images", [])
        if images:
            return images[0].get("src")
        return None

    async def _get_remaining_products_count(self, merchant: Merchant) -> int:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://{merchant.shopify_domain}/admin/api/{settings.SHOPIFY_API_VERSION}/products/count.json",
                headers={"X-Shopify-Access-Token": merchant.access_token},
                params={"status": "active"}
            )
            if response.status_code == 200:
                return response.json().get("count", 0)
            return 0
            
    async def _generate_quick_proposals_fallback(self, merchant_id, products, session):
         # Logic from original task to ensure we populate inbox if strategy agent didn't
         for product in products:
            # Check if exists
            exists = await session.execute(select(InboxItem).where(
                InboxItem.merchant_id == merchant_id,
                InboxItem.proposal_data['product_title'].as_string() == product['title']
            ))
            if exists.scalar_one_or_none(): continue

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
