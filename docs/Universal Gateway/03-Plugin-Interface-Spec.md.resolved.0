# Universal Gateway: Plugin Interface Specification

This defines the contract that all Channel Plugins must implement. It uses Python's `Protocol` for structural typing.

## The Protocol

```python
from typing import Protocol, Dict, List, Optional
from datetime import datetime

class ChannelPlugin(Protocol):
    """
    Contract for a Universal Gateway Channel Integration.
    Implementation examples: 'twilio', 'meta_whatsapp', 'sendgrid', 'slack_app'.
    """
    
    @property
    def channel_id(self) -> str:
        """Unique identifier (e.g. 'whatsapp')."""
        ...
        
    async def configure(self, settings: Dict) -> None:
        """
        Called on startup to inject secrets/config.
        
        Args:
            settings: Dict containing API keys, webhook secrets, etc.
        """
        ...
        
    async def send_message(self, target_id: str, content: str, **kwargs) -> str:
        """
        Sends an outbound message.
        
        Args:
            target_id: The provider-specific ID (e.g. phone number, email, slack user ID).
                      Extracted from the session_key (e.g., 'whatsapp:+1555' -> '+1555').
            content: Text content to send.
            
        Returns:
            provider_message_id: The external ID/receipt for the message.
        """
        ...
        
    async def validate_webhook(self, request: object) -> bool:
        """
        Validates that an incoming webhook request is authentic.
        """
        ...
        
    async def parse_webhook(self, request: object) -> 'InboundMessage':
        """
        Converts a raw provider HTTP request into a normalized InboundMessage.
        """
        ...
```

## Example Implementation: Twilio SMS

```python
class TwilioSMSPlugin:
    def __init__(self):
        self._client = None
        self._from_number = None
        
    @property
    def channel_id(self) -> str:
        return "sms"
        
    async def configure(self, settings: Dict):
        from twilio.rest import Client
        self._client = Client(settings['SID'], settings['TOKEN'])
        self._from_number = settings['FROM_NUMBER']
        
    async def send_message(self, target_id: str, content: str, **kwargs) -> str:
        msg = self._client.messages.create(
            body=content,
            from_=self._from_number,
            to=target_id
        )
        return msg.sid
        
    async def parse_webhook(self, request) -> InboundMessage:
        form = await request.form()
        return InboundMessage(
            channel_id="sms",
            session_key=f"sms:{form['From']}",
            content=form['Body'],
            ...
        )
```
