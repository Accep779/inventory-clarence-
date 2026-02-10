import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.agents.strategy import StrategyAgent
from app.models import Product, ProductVariant

@pytest.mark.asyncio
async def test_calculate_pricing_missing_cost_fallback():
    """
    Verify 40% margin fallback when cost is None.
    """
    # Setup
    agent = StrategyAgent("mock_merchant")
    
    # Mock Product with NO COST
    product = MagicMock(spec=Product)
    product.id = "prod_123"
    product.title = "Test Product"
    product.cost_per_unit = None  # CRITICAL: Missing Cost
    
    # Mock One Variant
    variant = MagicMock(spec=ProductVariant)
    variant.price = 100.00
    product.variants = [variant]
    
    # Mock Floor Pricing Service (return None/False)
    # We need to mock the service instantiation inside the method or patch it
    # Original behavior would raise ValueError.
    # We proceed to test the NEW behavior below.

    # We need to patch FloorPricingService where it is defined,
    # because it is locally imported inside the method.
    with patch('app.services.floor_pricing.FloorPricingService') as MockFloor, \
         patch('app.agents.strategy.async_session_maker') as MockSession:
        
        # Setup mocks
        floor_instance = MockFloor.return_value
        floor_instance.get_floor_price = AsyncMock(return_value=None)
        floor_instance.can_liquidate = AsyncMock(return_value=False)
        floor_instance.check_margin_compliance = AsyncMock(return_value=MagicMock(is_compliant=True))
        
        # Run calculation with "flash_sale" (30-50% discount)
        pricing = await agent._calculate_pricing(product, "flash_sale")
        
        # ASSERTIONS
        # 1. Cost should be estimated at 60% of price (100 * 0.6 = 60.0)
        assert pricing['cost'] == 60.0
        
        # 2. Sale price should be discounted from 100
        # Flash sale is 30% discount -> $70
        # Margin check: (70 - 60) / 70 = 14% margin (positive)
        assert pricing['sale_price'] < 100.0
        assert pricing['margin_percent'] > 0
        
        print(f"✅ Verified: Cost {pricing['cost']} derived from Price 100.0")
