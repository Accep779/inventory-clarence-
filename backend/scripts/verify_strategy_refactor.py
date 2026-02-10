import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), ".."))

from app.database import async_session_maker
from app.models import Merchant, Product, ProductVariant
from sqlalchemy import select
from app.agents.strategy import StrategyAgent
from uuid import uuid4

# Mock product for test
class MockProduct:
    def __init__(self, id, title):
        self.id = id
        self.title = title

async def verify_refactor():
    """
    Test the Refactored StrategyAgent.
    It should:
    1. Authenticate (hit internal API)
    2. Create Proposal (hit internal API)
    3. Return valid InboxItem proxy
    """
    print("\n🕵️ Starting Strategy Agent Refactor Verification...")
    
    # 1. Setup Context
    async with async_session_maker() as session:
        result = await session.execute(select(Merchant).limit(1))
        merchant = result.scalar_one_or_none()
        
        # Need a real product for the API payload validation to make sense logistically
        # but for the unit test of _create_proposal we can pass a mock if flexible
        prod_res = await session.execute(select(Product).limit(1))
        product = prod_res.scalar_one_or_none()
        
        if not product:
            print("❌ No product found")
            return

    agent = StrategyAgent(merchant.id)
    
    # 2. Test Authentication (internal method)
    print("🔑 Testing Authentication...")
    await agent._authenticate()
    
    if agent._api_token:
        print(f"✅ Authenticated! Token: {agent._api_token[:10]}...")
    else:
        print("❌ Authentication Failed")
        return

    # 3. Test Proposal Creation (internal method)
    print("📝 Testing Proposal Creation via API...")
    try:
        data = {
            'product': product,
            'strategy': 'flash_sale',
            'pricing': {'original_price': 100, 'sale_price': 80, 'discount_percent': 20},
            'audience': {'segments': ['vip'], 'total_customers': 50},
            'copy': {'email_subject': 'Test'},
            'projections': {'revenue': 1000},
            'execution_id': str(uuid4()),
            'session': None # API doesn't use session anymore!
        }
        
        item = await agent._create_proposal(**data)
        
        if item.id and item.status == 'created':
             print(f"✅ Proposal Created via API! ID: {item.id}")
        else:
             print(f"❌ Invalid Response: {item}")
             
    except Exception as e:
        print(f"❌ Proposal Creation Error: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_refactor())
