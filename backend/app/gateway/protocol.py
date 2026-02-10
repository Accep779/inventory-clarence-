from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from datetime import datetime

class InboundMessage(BaseModel):
    """
    Normalized inbound message from any channel.
    """
    id: str
    channel_id: str         # e.g. 'whatsapp', 'email'
    session_key: str        # e.g. 'whatsapp:+1555...', 'email:bob@example.com'
    sender_name: Optional[str] = None
    content: str
    attachments: List[str] = [] # List of URLs
    timestamp: datetime = datetime.utcnow()
    raw_payload: Dict[str, Any] = {}

class ChannelPlugin(ABC):
    """
    The Protocol that all Channel Plugins must implement.
    """
    
    @property
    @abstractmethod
    def channel_id(self) -> str:
        """Unique identifier (e.g., 'twilio_sms', 'sendgrid_email')."""
        pass

    @abstractmethod
    async def send_message(self, session_key: str, content: str, **kwargs) -> str:
        """
        Send a message to the user.
        Returns: The provider's message ID.
        """
        pass

    @abstractmethod
    async def validate_webhook(self, request: Any) -> Optional[InboundMessage]:
        """
        Parse and validate an incoming webhook request.
        Returns: Normalized InboundMessage or None if invalid.
        """
        pass
