
import pytest
from app.adapters.registry import AdapterRegistry, UnsupportedPlatformError
from app.adapters.shopify import ShopifyPlatformAdapter
from app.adapters.base import BasePlatformAdapter

def test_registry_resolution():
    """Verify AdapterRegistry resolves Shopify correctly."""
    adapter = AdapterRegistry.get_adapter("shopify")
    assert isinstance(adapter, ShopifyPlatformAdapter)
    assert isinstance(adapter, BasePlatformAdapter)

def test_registry_resolution_case_insensitive():
    """Verify registry raises error for unknown casing (default behavior)."""
    with pytest.raises(UnsupportedPlatformError):
         AdapterRegistry.get_adapter("Shopify") 

def test_registry_unknown_platform():
    """Verify unknown platform raises error."""
    with pytest.raises(UnsupportedPlatformError):
        AdapterRegistry.get_adapter("unknown_platform")
