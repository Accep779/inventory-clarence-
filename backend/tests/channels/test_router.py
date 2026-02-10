
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.channels.router import ChannelRouter
from app.channels.base import BaseExternalChannel
# from app.models import Merchant # Mocking merchant instead

# Mock Channels
class MockeBay(BaseExternalChannel):
    channel_name = "ebay"
    async def authenticate(self, c): return {}
    async def create_listing(self, *args, **kwargs): return None
    async def monitor_listing(self, *args, **kwargs): return None
    async def cancel_listing(self, *args, **kwargs): return True
    async def sync_sales(self, *args, **kwargs): return []

class MockAmazon(BaseExternalChannel):
    channel_name = "amazon"
    async def authenticate(self, c): return {}
    async def create_listing(self, *args, **kwargs): return None
    async def monitor_listing(self, *args, **kwargs): return None
    async def cancel_listing(self, *args, **kwargs): return True
    async def sync_sales(self, *args, **kwargs): return []

@pytest.fixture
def merchant():
    m = MagicMock()
    m.external_channels_enabled = True
    m.external_excluded_categories = []
    m.enabled_external_channels = ["ebay", "amazon"]
    return m

@pytest.fixture
def router(merchant):
    with patch("app.channels.registry.CHANNEL_REGISTRY", {"ebay": MockeBay, "amazon": MockAmazon}):
        return ChannelRouter(merchant)


def test_routing_store_only_low_stock(router):
    product = {
        "stock_quantity": 10,
        "days_since_last_sale": 5,
        "category": "Apparel"
    }
    proposal = {"proposed_price": Decimal("10.00")}
    
    routing = router.route(product, proposal)
    
    assert routing["store"] is True
    assert len(routing["external_channels"]) == 0
    assert "store-only thresholds" in routing["reasoning"]

def test_routing_both_channels_moderate(router):
    product = {
        "stock_quantity": 30,
        "days_since_last_sale": 20,
        "category": "Apparel"
    }
    proposal = {"proposed_price": Decimal("10.00")}
    
    routing = router.route(product, proposal)
    
    assert routing["store"] is True
    assert len(routing["external_channels"]) == 2 # eBay and Amazon
    # 40% of 30 = 12. Split 6 each.
    assert routing["external_channels"][0]["allocated_units"] == 6

def test_routing_both_channels_dead_stock(router):
    product = {
        "stock_quantity": 100,
        "days_since_last_sale": 45,
        "category": "Apparel"
    }
    proposal = {"proposed_price": Decimal("10.00")}
    
    routing = router.route(product, proposal)
    
    assert routing["store"] is True
    # 70% of 100 = 70. Split 35 each.
    assert len(routing["external_channels"]) == 2
    assert sum(c["allocated_units"] for c in routing["external_channels"]) == 70

def test_routing_excluded_category(router):
    router.merchant.external_excluded_categories = ["Electronics"]
    
    product = {
        "stock_quantity": 100,
        "days_since_last_sale": 45,
        "category": "Electronics"
    }
    proposal = {"proposed_price": Decimal("10.00")}
    
    routing = router.route(product, proposal)
    
    assert routing["store"] is True
    assert len(routing["external_channels"]) == 0
    assert "excluded" in routing["reasoning"]

def test_routing_disabled_globally(router):
    router.merchant.external_channels_enabled = False
    
    product = {
        "stock_quantity": 100,
        "days_since_last_sale": 45,
        "category": "Apparel"
    }
    proposal = {"proposed_price": Decimal("10.00")}
    
    routing = router.route(product, proposal)
    
    assert len(routing["external_channels"]) == 0
