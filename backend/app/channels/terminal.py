from typing import Any, Optional
from app.gateway.protocol import ChannelPlugin, InboundMessage
from app.gateway.registry import PluginRegistry
import uuid

class TerminalPlugin(ChannelPlugin):
    """
    DEBUG PLUGIN: Prints outbound messages to stdout.
    Accepts any inbound webhook for testing.
    """
    
    @property
    def channel_id(self) -> str:
        return "terminal"

    async def send_message(self, session_key: str, content: str, **kwargs) -> str:
        print(f"\n[📟 TERMINAL OUTBOUND] To: {session_key}\n   '{content}'\n")
        return f"mock_msg_id_{uuid.uuid4()}"

    async def validate_webhook(self, request: Any) -> Optional[InboundMessage]:
        # Simple mock validation for testing
        data = request if isinstance(request, dict) else {}
        return InboundMessage(
            id=str(uuid.uuid4()),
            channel_id="terminal",
            session_key=data.get("from", "unknown_user"),
            content=data.get("text", ""),
            raw_payload=data
        )

# Auto-register on import (wrapped for import safety)
try:
    PluginRegistry.register(TerminalPlugin())
except Exception as e:
    print(f"Warning: Failed to register TerminalPlugin: {e}")
