import asyncio
import uuid
from decimal import Decimal
from app.agents.strategy import StrategyAgent
from app.database import async_session_maker
from app.models import Merchant, Product, ProductVariant, InboxItem

async def main():
    merchant_id = "test_merchant_autonomy"
    product_id = str(uuid.uuid4())
    
    print(f"🧪 Testing Content Idempotency for Product {product_id}...")
    
    async with async_session_maker() as session:
        # 1. Setup Data
        merchant = Merchant(id=merchant_id, domain="test.com", access_token="test", created_at=None)
        product = Product(
             id=product_id, merchant_id=merchant_id, title="Test Product", 
             product_type="Shirt", total_inventory=100, shopify_product_id="123",
             dead_stock_severity="critical"
        )
        variant = ProductVariant(id=str(uuid.uuid4()), product_id=product_id, price=Decimal("50.00"), inventory_quantity=100)
        
        # Merge if exists mechanism or just try/except (simplified for script)
        session.merge(merchant)
        session.add(product)
        session.add(variant)
        
        # 2. Create Existing Proposal
        proposal = InboxItem(
            merchant_id=merchant_id,
            type="clearance_proposal",
            status="pending",
            agent_type="strategy",
            proposal_data={"product_id": product_id}, # Key field for idempotency check
            confidence=Decimal("90")
        )
        session.add(proposal)
        await session.commit()
    
    # 3. Trigger Strategy Agent
    agent = StrategyAgent(merchant_id)
    try:
        result = await agent.plan_clearance(product_id)
        
        if result.get("status") == "skipped" and result.get("reason") == "Active proposal exists":
             print("✅ PASS: StrategyAgent correctly skipped existing proposal.")
        else:
             print(f"❌ FAIL: StrategyAgent did not skip. Result: {result}")
             
    except Exception as e:
        print(f"❌ FAIL: Exception occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
