"""
ChannelRegistry — Resolves available external channels for a merchant.

Similar to AdapterRegistry for platform adapters, but for external
listing channels. A merchant can enable/disable channels in Settings.
"""

from typing import Dict, List, Type, Any
from app.channels.base import BaseExternalChannel
# Note: Imports will be added as channels are implemented
# from app.channels.ebay import eBayChannel
# from app.channels.amazon import AmazonChannel


CHANNEL_REGISTRY: Dict[str, Any] = {
    # "ebay": eBayChannel,
    # "amazon": AmazonChannel,
}


class ChannelRegistry:

    @staticmethod
    def get_enabled_channels(merchant: Any) -> List[BaseExternalChannel]:
        """
        Return instances of all channels the merchant has enabled
        and authenticated with.
        """
        # merchant is a database model object (Merchant) or dict
        # Assuming dict-like access or attribute access handled via getattr/get
        
        # Safe access for dict or object
        enabled = []
        if isinstance(merchant, dict):
            enabled = merchant.get("enabled_external_channels", [])
        else:
            enabled = getattr(merchant, "enabled_external_channels", []) or []
            
        channels = []
        for name in enabled:
            channel_class = CHANNEL_REGISTRY.get(name)
            if channel_class:
                channels.append(channel_class())
        return channels

    @staticmethod
    def available_channels() -> list:
        return list(CHANNEL_REGISTRY.keys())
        
    @classmethod
    def register(cls, name: str, channel_class: Type[BaseExternalChannel]):
        """Dynamically register a channel."""
        CHANNEL_REGISTRY[name] = channel_class
        
    @staticmethod
    def get_channel(name: str) -> BaseExternalChannel:
        """Get a specific channel instance by name."""
        channel_class = CHANNEL_REGISTRY.get(name)
        if not channel_class:
            # Lazy loading fallback
            if name == "ebay":
                from app.channels.ebay import eBayChannel
                CHANNEL_REGISTRY["ebay"] = eBayChannel
                channel_class = eBayChannel
            elif name == "amazon":
                from app.channels.amazon import AmazonChannel
                CHANNEL_REGISTRY["amazon"] = AmazonChannel
                channel_class = AmazonChannel
        
        if not channel_class:
            raise ValueError(f"Channel '{name}' is not supported.")
            
        return channel_class()
