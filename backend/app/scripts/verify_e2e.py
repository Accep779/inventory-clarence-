import asyncio
import uuid
from decimal import Decimal
from datetime import datetime
import os

# [FIX] Mock Encryption Key if missing for local test
if "ENCRYPTION_KEY" not in os.environ:
    os.environ["ENCRYPTION_KEY"] = "mock_key_for_testing_purposes_only_123"

from app.database import async_session_maker
from app.models import Merchant, Product, ProductVariant, InboxItem
from temporalio.client import Client

# Ensure PYTHONPATH includes backend
# Run with: $env:PYTHONPATH="backend"; python backend/app/scripts/verify_e2e.py

async def main():
    print("🚀 Starting End-to-End Verification (Ghost Shopper)...")
    
    merchant_id = "test_merchant_e2e"
    session_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())
    
    # 1. Inject Stale Data
    print(f"📦 Injecting Stale Product ({product_id})...")
    async with async_session_maker() as session:
        merchant = Merchant(id=merchant_id, domain="test-e2e.com", access_token="test_token", created_at=datetime.utcnow())
        
        # Create a product that IS dead stock (Critical severity)
        product = Product(
             id=product_id, 
             merchant_id=merchant_id, 
             title="E2E Stale Winter Jacket", 
             product_type="Apparel", 
             total_inventory=500, # High inventory
             shopify_product_id="999888777",
             dead_stock_severity="critical", # Force logic to pick it up
             velocity_score=10.0,
             days_since_last_sale=180,
             is_dead_stock=True
        )
        variant = ProductVariant(id=str(uuid.uuid4()), product_id=product_id, price=Decimal("150.00"), inventory_quantity=500)
        
        await session.merge(merchant)
        await session.merge(product)
        await session.merge(variant)
        await session.commit()
        print("✅ Data Injected.")

    # 2. Trigger Temporal Workflow (The Scheduler)
    print("⚡ Triggering QuickScanWorkflow via Temporal...")
    try:
        client = await Client.connect("localhost:7233")
        
        handle = await client.start_workflow(
            "QuickScanWorkflow",
            {"merchant_id": merchant_id, "session_id": session_id},
            id=f"e2e-test-{session_id}",
            task_queue="execution-agent-queue"
        )
        print(f"✅ Workflow started (ID: {handle.id})")
        
        # We can wait for result, but QuickScanWorkflow returns a summary. 
        # The REAL test is if it generated an InboxItem.
        print("⏳ Waiting for workflow result...")
        result = await handle.result()
        print(f"📋 Workflow Result: {result}")
        
    except Exception as e:
        print(f"❌ Temporal Trigger Failed: {e}")
        return

    # 3. Verify Inbox Item (The Autonomy)
    print("🔍 Checking for Proposal in Inbox...")
    max_retries = 10
    found = False
    
    for i in range(max_retries):
        await asyncio.sleep(2) # Poll every 2s
        async with async_session_maker() as session:
            # Check for ANY proposal for this product created recently
            from sqlalchemy import select
            stmt = select(InboxItem).where(
                InboxItem.merchant_id == merchant_id,
                InboxItem.proposal_data['product_id'].as_string() == product_id
            )
            item = (await session.execute(stmt)).scalars().first()
            
            if item:
                print(f"✅ SUCCESS: Inbox Item Found! (ID: {item.id})")
                print(f"   - Type: {item.type}")
                print(f"   - Status: {item.status}")
                print(f"   - Strategy: {item.proposal_data.get('strategy_name')}")
                found = True
                break
        print(f"   ... polling ({i+1}/{max_retries})")
        
    if not found:
        print("❌ FAILED: No proposal created after 20 seconds.")
    else:
        print("🎉 END-TO-END VERIFICATION COMPLETE. The system is Autonomous.")

if __name__ == "__main__":
    asyncio.run(main())
