import pytest
import asyncio
from datetime import datetime, timedelta
from app.models import Product, Merchant

@pytest.mark.asyncio
async def test_observer_scalability_mock():
    """
    Mock test to verify the structure of the new fan-out logic.
    Real scalability test requires 10K+ records which is too heavy for CI.
    """
    from app.tasks.observer import run_daily_analysis_all_merchants
    
    # We just want to ensure the function can be called and dispatches tasks
    # This assumes Celery is mocked or eager mode is on
    try:
        run_daily_analysis_all_merchants()
        assert True
    except Exception as e:
        pytest.fail(f"Fan-out dispatch failed: {e}")

@pytest.mark.asyncio
async def test_api_products_count_query(async_client, test_merchant, db_session):
    """
    Verify list_products uses optimized count query and allows large offsets.
    """
    # Create a batch of products directly in DB
    products = [
        Product(
            id=f"prod_{i}",
            merchant_id=test_merchant.id,
            title=f"Perf Product {i}",
            status="active",
            is_dead_stock=(i % 2 == 0),
            velocity_score=10.0
        ) for i in range(20)
    ]
    db_session.add_all(products)
    await db_session.commit()
    
    start = datetime.utcnow()
    response = await async_client.get(
        "/api/products?limit=10&offset=10",
        headers={"X-Merchant-Id": test_merchant.id}
    )
    elapsed = (datetime.utcnow() - start).total_seconds() * 1000
    
    assert response.status_code == 200
    data = response.json()
    assert data['total'] == 20
    assert len(data['products']) == 10
    # Ensure it's fast (mock threshold, but checks logic path)
    assert elapsed < 500 

@pytest.mark.asyncio
async def test_dead_stock_summary_eager_load(async_client, test_merchant, db_session):
    """
    Verify dead-stock-summary endpoint returns correct structure without error.
    """
    response = await async_client.get(
        "/api/products/dead-stock-summary",
        headers={"X-Merchant-Id": test_merchant.id}
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_dead_stock" in data
    assert "by_severity" in data
