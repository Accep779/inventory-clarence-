"""
AdapterRegistry — Resolves the correct platform adapter for a given merchant.

When ExecutionAgent needs to update a price, it does not say
"call ShopifyService". It says "get me the adapter for this merchant"
and calls update_price() on whatever comes back.

This file is where new platforms are registered. Adding WooCommerce
support means adding one line here and one new adapter file.
Nothing else changes.
"""

from typing import Dict, Type, List
from app.adapters.base import BasePlatformAdapter
# Lazy imports are handled inside get_adapter to avoid circular dependencies if any
# but ideally we import them here if they are clean.
# We will import ShopifyPlatformAdapter inside the method or at top if available.

class UnsupportedPlatformError(Exception):
    """Raised when a merchant's platform is not in the registry."""
    pass

class AdapterRegistry:
    # We'll populate this dynamically or import safely
    _REGISTRY: Dict[str, Type[BasePlatformAdapter]] = {}

    @classmethod
    def register(cls, name: str, adapter_cls: Type[BasePlatformAdapter]):
        """Register a new platform adapter."""
        cls._REGISTRY[name] = adapter_cls

    @classmethod
    def get_adapter(cls, platform_name: str) -> BasePlatformAdapter:
        """
        Return an instance of the correct adapter for the given platform.

        Raises:
            UnsupportedPlatformError if the platform is not in the registry.
        """
        # Ensure 'shopify' is registered.
        # In a real app we might use a plugin system or import at module level.
        # For now, we'll force import if missing (lazy loading pattern)
        if platform_name == 'shopify' and 'shopify' not in cls._REGISTRY:
            from app.adapters.shopify import ShopifyPlatformAdapter
            cls.register('shopify', ShopifyPlatformAdapter)

        if platform_name == 'woocommerce' and 'woocommerce' not in cls._REGISTRY:
            from app.adapters.woocommerce import WooCommercePlatformAdapter
            cls.register('woocommerce', WooCommercePlatformAdapter)

        if platform_name == 'bigcommerce' and 'bigcommerce' not in cls._REGISTRY:
            from app.adapters.bigcommerce import BigCommercePlatformAdapter
            cls.register('bigcommerce', BigCommercePlatformAdapter)

        adapter_class = cls._REGISTRY.get(platform_name)
        if adapter_class is None:
            raise UnsupportedPlatformError(
                f"Platform '{platform_name}' is not supported. "
                f"Supported platforms: {list(cls._REGISTRY.keys())}"
            )
        return adapter_class()

    @classmethod
    def supported_platforms(cls) -> List[str]:
        """Return the list of currently supported platform names."""
        # Ensure at least shopify is potentially registered
        return list(cls._REGISTRY.keys()) or ['shopify']
