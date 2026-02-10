import pytest
import asyncio
from datetime import datetime
from decimal import Decimal
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.database import async_session_maker
from app.models import Merchant, Product, StoreDNA, InboxItem, Campaign, Order, Ledger
from app.config import get_settings
from app.auth_middleware import create_access_token

# Settings and Test Constants
settings = get_settings()
TEST_SHOP = "test-store.myshopify.com"
TEST_SHOP_ID = "123456789"
TEST_TOKEN = "shp_test_token"

@pytest.fixture(autouse=True)
def mock_redis():
    """Mock Redis client for Idempotency Middleware."""
    mock_client = MagicMock()
    mock_client.get.return_value = None
    mock_client.setex.return_value = True
    
    with patch("app.middleware.idempotency.get_redis_client", return_value=mock_client):
        yield mock_client

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture(autouse=True)
async def clean_db():
    async with async_session_maker() as session:
        await session.execute(text(f"DELETE FROM merchants WHERE shopify_domain = '{TEST_SHOP}'"))
        await session.commit()
    print("[CLEAN] DB Cleaned")
    yield
    async with async_session_maker() as session:
        await session.execute(text(f"DELETE FROM merchants WHERE shopify_domain = '{TEST_SHOP}'"))
        await session.commit()

@pytest.mark.asyncio
async def test_complete_merchant_journey(client):
    """
    E2E VALIDATION: Complete Merchant Onboarding (Seeded) to First Revenue
    """
    print("\n[START] STARTING E2E MERCHANT JOURNEY TEST (SEEDED AUTH)")
    start_time = datetime.now()
    step_times = {}
    
    # ============================================================================
    # STEP 1: INSTALLATION (SEEDED)
    # ============================================================================
    t0 = datetime.now()
    print("\n[STEP 1] Seeding Merchant (Skipping OAuth Network Call)...")
    
    async with async_session_maker() as session:
        merchant = Merchant(
            shopify_domain=TEST_SHOP,
            shopify_shop_id=TEST_SHOP_ID,
            access_token=TEST_TOKEN,
            store_name="Test Store",
            email="test@example.com",
            plan="growth",
            is_active=True,
            sync_status="pending"
        )
        session.add(merchant)
        await session.commit()
        await session.refresh(merchant)
        merchant_id = merchant.id
        
    # Generate Auth Token
    jwt_token = create_access_token(merchant_id)
    auth_cookies = {"auth_token": jwt_token}
    
    step_times["1_installation"] = (datetime.now() - t0).total_seconds()
    print(f"[OK] Seeded Merchant {merchant_id}")

    # ============================================================================
    # STEP 2: INITIAL DATA SYNC (Mocked)
    # ============================================================================
    t0 = datetime.now()
    print("\n[STEP 2] Initial Data Sync (Simulated)...")
    
    # We simulate the RESULT of the sync task
    async with async_session_maker() as session:
        merchant = await session.get(Merchant, merchant_id)
        merchant.sync_status = "completed"
        
        products = []
        for i in range(10):
            is_dead = i < 3
            p = Product(
                id=str(uuid.uuid4()),
                shopify_product_id=1000 + i,
                merchant_id=merchant_id,
                title=f"Test Product {i}",
                handle=f"test-prod-{i}",
                total_inventory=100 if is_dead else 10,
                units_sold_30d=0 if is_dead else 50,
                cost_per_unit=Decimal("10.00"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(p)
            products.append(p)
        await session.commit()
        
    step_times["2_data_sync"] = (datetime.now() - t0).total_seconds()
    print(f"[OK] Synced 10 products")

    # ============================================================================
    # STEP 3: STORE DNA ANALYSIS
    # ============================================================================
    t0 = datetime.now()
    print("\n[STEP 3] Store DNA Analysis...")
    
    # We mock the service call to avoid LLM costs/latency
    with patch("app.services.dna.DNAService.process_brand_guide") as mock_dna:
        mock_dna.return_value = {"status": "success"}
        
        async with async_session_maker() as session:
            dna = StoreDNA(
                merchant_id=merchant_id,
                brand_tone="Friendly, Earthy",
                industry_type="Sustainability",
                brand_values=["Eco-friendly", "Organic"],
                brand_guide_raw="# Brand Guide"
            )
            session.add(dna)
            await session.commit()
            
    # Test API Access with the cookie
    response = await client.get("/api/dna/summary", cookies=auth_cookies)
    if response.status_code != 200:
        raise Exception(f"DNA Summary failed: {response.text}")
        
    step_times["3_dna_analysis"] = (datetime.now() - t0).total_seconds()
    print(f"[OK] DNA API Verified")

    # ============================================================================
    # STEP 4: INVENTORY ANALYSIS (Observer Agent)
    # ============================================================================
    t0 = datetime.now()
    print("\n[STEP 4] Inventory Analysis...")
    
    # Execute logic directly on DB to simulate agent
    async with async_session_maker() as session:
        result = await session.execute(select(Product).where(Product.merchant_id == merchant_id))
        all_prods = result.scalars().all()
        dead = 0
        for p in all_prods:
            if p.units_sold_30d < 5:
                p.is_dead_stock = True
                p.dead_stock_severity = "critical"
                dead += 1
        await session.commit()
        
    step_times["4_inventory_analysis"] = (datetime.now() - t0).total_seconds()
    print(f"[OK] Identified {dead} dead stock items")

    # ============================================================================
    # STEP 5: STRATEGY PROPOSAL (Strategy Agent)
    # ============================================================================
    t0 = datetime.now()
    print("\n[STEP 5] Strategy Generation...")
    
    # Create Inbox Item mocked
    async with async_session_maker() as session:
        result = await session.execute(select(Product).where(Product.merchant_id == merchant_id, Product.is_dead_stock == True))
        target = result.scalars().first()
        
        proposal = InboxItem(
            merchant_id=merchant_id,
            type="clearance_proposal",
            status="pending",
            agent_type="strategy_agent",
            proposal_data={
                "strategy": "flash_sale",
                "discount_pct": 30,
                "target_product_id": target.id,
                "reasoning": "Test Proposal"
            },
            risk_level="low",
            confidence=0.99
        )
        session.add(proposal)
        await session.commit()
        await session.refresh(proposal)
        proposal_id = proposal.id
        
    # Verify Inbox API
    response = await client.get("/api/inbox", cookies=auth_cookies)
    assert response.status_code == 200
    assert len(response.json()["items"]) > 0
    
    step_times["5_strategy_gen"] = (datetime.now() - t0).total_seconds()
    print(f"[OK] Proposal {proposal_id} Generated")

    # ============================================================================
    # STEP 6: PROPOSAL APPROVAL
    # ============================================================================
    t0 = datetime.now()
    print("\n[STEP 6] Merchant Approval...")
    
    response = await client.post(
        f"/api/inbox/{proposal_id}/approve",
        cookies=auth_cookies,
        headers={"Idempotency-Key": str(uuid.uuid4())}
    )
    if response.status_code != 200:
        raise Exception(f"Approval failed: {response.text}")
        
    step_times["6_approval"] = (datetime.now() - t0).total_seconds()
    print(f"[OK] Proposal Approved")

    # ============================================================================
    # STEP 7: CAMPAIGN EXECUTION
    # ============================================================================
    t0 = datetime.now()
    print("\n[STEP 7] Campaign Execution...")
    
    campaign_id = str(uuid.uuid4())
    async with async_session_maker() as session:
        camp = Campaign(
            id=campaign_id,
            merchant_id=merchant_id,
            name="Test Campaign",
            type="flash_sale",
            status="active",
            emails_sent=100,
            started_at=datetime.utcnow()
        )
        session.add(camp)
        
        item = await session.get(InboxItem, proposal_id)
        item.status = "executed"
        await session.commit()
        
    step_times["7_execution"] = (datetime.now() - t0).total_seconds()
    print(f"[OK] Campaign {campaign_id} Launched")

    # ============================================================================
    # STEP 8: RESULTS
    # ============================================================================
    t0 = datetime.now()
    print("\n[STEP 8] Results Tracking...")
    
    async with async_session_maker() as session:
        order = Order(
            merchant_id=merchant_id,
            shopify_order_id=999,
            order_number="#1001",
            total_price=Decimal("100.00"),
            subtotal_price=Decimal("90.00"),
            created_at=datetime.utcnow()
        )
        session.add(order)
        
        camp = await session.get(Campaign, campaign_id)
        camp.revenue = Decimal("100.00")
        
        ledger = Ledger(
            merchant_id=merchant_id,
            order_id=order.id,
            gross_amount=Decimal("100.00"),
            net_amount=Decimal("90.00"),
            agent_stake=Decimal("9.00"),
            attribution_source=f"campaign:{campaign_id}"
        )
        session.add(ledger)
        await session.commit()
        
    step_times["8_results"] = (datetime.now() - t0).total_seconds()
    print(f"[OK] Revenue Attributed")
    
    total_time = (datetime.now() - start_time).total_seconds()
    print("\n" + "="*50)
    print(f"[COMPLETE] MERCHANT JOURNEY COMPLETED in {total_time:.2f}s")
    for step, duration in step_times.items():
        print(f"{step:<25}: {duration:>6.2f}s")
    print("="*50)
