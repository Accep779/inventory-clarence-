
import pytest
from app.adapters.registry import AdapterRegistry
from app.adapters.base import BasePlatformAdapter
from app.adapters.woocommerce import WooCommercePlatformAdapter
from app.adapters.bigcommerce import BigCommercePlatformAdapter

def test_registry_woocommerce_resolution():
    """Verify AdapterRegistry resolves WooCommerce correctly."""
    adapter = AdapterRegistry.get_adapter("woocommerce")
    assert isinstance(adapter, WooCommercePlatformAdapter)
    assert isinstance(adapter, BasePlatformAdapter)
    assert adapter.platform_name == "woocommerce"

def test_registry_bigcommerce_resolution():
    """Verify AdapterRegistry resolves BigCommerce correctly."""
    adapter = AdapterRegistry.get_adapter("bigcommerce")
    assert isinstance(adapter, BigCommercePlatformAdapter)
    assert isinstance(adapter, BasePlatformAdapter)
    assert adapter.platform_name == "bigcommerce"

def test_adapter_interfaces():
    """Verify adapters have required methods (inheritance check)."""
    # This is implicitly checked by instantiation since abstract methods must be implemented,
    # but we can explicitly check method existence if needed.
    
    woo = WooCommercePlatformAdapter()
    assert hasattr(woo, 'authenticate')
    assert hasattr(woo, 'sync_products')
    
    bigc = BigCommercePlatformAdapter()
    assert hasattr(bigc, 'authenticate')
    assert hasattr(bigc, 'sync_products')
