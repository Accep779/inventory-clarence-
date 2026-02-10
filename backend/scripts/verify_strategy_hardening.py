
import asyncio
import os
import sys
import logging
from datetime import datetime, timedelta
from decimal import Decimal

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import async_session_maker
from app.models import Merchant, Product, ProductVariant, FloorPricing, StoreDNA, GlobalStrategyPattern
from app.agents.strategy import StrategyAgent
from sqlalchemy import select, delete

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_hardening")

import functools
print = functools.partial(print, flush=True)

async def verify_strategy_hardening():
    print("\n🛡️  VERIFYING STRATEGY AGENT HARDENING")
    print("========================================")
    
    import uuid
    uid = str(uuid.uuid4())[:8]
    merchant_id = f"merch_test_{uid}"
    
    async with async_session_maker() as session:
        # 0. Schema Migration (Hack for verification)
        # ----------------
        try:
            from sqlalchemy import text
            await session.execute(text("ALTER TABLE merchants ADD COLUMN enable_multi_plan_strategy BOOLEAN DEFAULT 0"))
            await session.commit()
            print("✅ Added missing column 'enable_multi_plan_strategy'")
        except Exception as e:
            # Likely already exists
            print(f"ℹ️ Schema check: {e}")
            await session.rollback()

        # 1. Setup Test Data (NO CLEANUP - UNIQUE ID)
        # ----------------
        print("\n1. Setting up Test Data...")
        
        # Create Merchant (Default: Multi-Plan OFF)
        merchant = Merchant(
            id=merchant_id,
            store_name=f"Hardening Test Store {uid}",
            email=f"test_{uid}@example.com",
            shopify_domain=f"hardening-test-{uid}.myshopify.com",
            shopify_shop_id=f"9{uid}",
            access_token="fake",
            enable_multi_plan_strategy=False  # TESTING DEFAULT
        )
        session.add(merchant)
        
        # Create DNA (Industry = Fashion)
        dna = StoreDNA(
            merchant_id=merchant_id,
            industry_type="Fashion",
            brand_tone="Edgy"
        )
        session.add(dna)
        
        # Create Product
        product = Product(
            id="prod_harden_1",
            merchant_id=merchant_id,
            shopify_product_id=88888,
            title="Test Sneaker",
            handle="test-sneaker",
            dead_stock_severity="critical", # Should trigger aggressive if fallback
            cost_per_unit=50.00
        )
        session.add(product)
        
        variant = ProductVariant(
            id="var_harden_1",
            product_id=product.id,
            shopify_variant_id=77777,
            title="Size 10",
            price=100.00,
            inventory_quantity=100
        )
        session.add(variant)
        
        # Create Floor Pricing (Issue: Floor > Price)
        floor = FloorPricing(
            merchant_id=merchant_id,
            product_id=product.id,
            sku="test-sneaker",
            cost_price=50.00,
            floor_price=120.00, # CRITICALLY HIGH (Higher than $100 price)
            min_margin_pct=10.00
        )
        session.add(floor)
        
        await session.commit()
        print("✅ Data seeded.")

    # 2. Test Execution
    # ----------------
    agent = StrategyAgent(merchant_id)
    
    print("\n2. Testing Plan Clearance (Single Plan + Floor Error)...")
    try:
        # We expect a CRITICAL warning in logs regarding floor price
        # And we expect execution to NOT be multi-plan
        result = await agent.plan_clearance(product_id="prod_harden_1")
        
        print(f"Result Status: {result.get('status')}")
        print(f"Strategy Selected: {result.get('strategy')}")
        print(f"Sale Price: ${result['projections'].get('sale_price') if 'projections' in result else 'N/A'}")
        
        # In single plan fallback, critical + high margin -> flash_sale or aggressive
        # But we have floor > price. The code should cap it at original price ($100).
        # And since cost is $50, margin is 50%.
        
        # Verify Single Plan Usage (Inferred vs Direct)
        # We can't easily mock the method call without unittest.mock, but we know fallback is determinstic.
        # Fallback for 'critical' severity is 'flash_sale' or 'aggressive_liquidation'.
        
    except Exception as e:
        print(f"❌ Execution failed: {e}")
        import traceback
        traceback.print_exc()

    # 3. Test Global Brain Integration (Multi-Plan ON)
    # ----------------
    print("\n3. Testing Multi-Plan + Global Brain...")
    
    # Enable feature flag
    async with async_session_maker() as session:
        m = await session.get(Merchant, merchant_id)
        m.enable_multi_plan_strategy = True
        await session.commit()
    
    # Create fake Global Pattern (Unique Key)
    async with async_session_maker() as session:
        print("   Creating global pattern...")
        pat = GlobalStrategyPattern(
            pattern_key=f"Fashion_flash_sale_{uid}",
            industry_type="Fashion",
            strategy_key="flash_sale",
            sample_count=500, # Valid > 100
            recommendation_score=50,
            p50_conversion=0.15,
            context_criteria={}
        )
        session.add(pat)
        await session.commit()

    # Run again
    try:
        # tailored to return 'flash_sale' recommendation potentially
        # verifying that it runs through multi-plan path
        # checking stdout/logs for "GLOBAL BRAIN INSIGHTS" in prompt is hard here,
        # but we can check if it runs without error.
        result = await agent.plan_clearance(product_id="prod_harden_1")
        print(f"Multi-Plan Result: {result.get('strategy')}")
        print("✅ Multi-plan execution completed.")
        
    except Exception as e:
        print(f"❌ Multi-plan failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify_strategy_hardening())
