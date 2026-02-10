from typing import Any, Optional
from app.gateway.protocol import ChannelPlugin, InboundMessage
from app.gateway.registry import PluginRegistry
import uuid

class EmailPlugin(ChannelPlugin):
    """
    EMAIL PLUGIN: Uses SMTP or SendGrid (Mocked for now).
    """
    
    @property
    def channel_id(self) -> str:
        return "email"

    async def send_message(self, session_key: str, content: str, **kwargs) -> str:
        # Check if we have SendGrid key, else print mock
        recipient = session_key.replace("email:", "")
        print(f"\n[📧 EMAIL SENT] To: {recipient} | Subject: Cephly Notification\n   '{content}'\n")
        return f"email_id_{uuid.uuid4()}"

    async def validate_webhook(self, request: Any) -> Optional[InboundMessage]:
        # Logic to parse SendGrid Inbound Parse Webhook would go here
        return None

# Auto-register on import
PluginRegistry.register(EmailPlugin())
