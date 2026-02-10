from typing import Dict, Type
from app.gateway.protocol import ChannelPlugin

class PluginRegistry:
    """
    Singleton registry to hold loaded Channel Plugins.
    """
    _instance = None
    _plugins: Dict[str, ChannelPlugin] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PluginRegistry, cls).__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, plugin: ChannelPlugin):
        """Register a specialized channel plugin."""
        cls._plugins[plugin.channel_id] = plugin
        print(f"[Gateway] Registered plugin: {plugin.channel_id}")

    @classmethod
    def get(cls, channel_id: str) -> ChannelPlugin:
        """Retrieve a plugin by ID."""
        if channel_id not in cls._plugins:
            raise ValueError(f"Channel plugin '{channel_id}' not found.")
        return cls._plugins[channel_id]

    @classmethod
    def list_channels(cls):
        return list(cls._plugins.keys())
