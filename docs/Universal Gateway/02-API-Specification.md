# Universal Gateway: API Specification

This document defines the HTTP endpoints and Internal Interfaces for the Universal Gateway.

## 1. External HTTP API (Webhooks)

These endpoints are exposed to the public internet to receive events from third-party platforms.

### `POST /gateway/webhook/{channel_id}`

**Description:** Generic receiver for all channel webhooks.
**Security:** Validates platform specific signatures (e.g., `X-Twilio-Signature`).

**Path Parameters:**
- `channel_id` (string): The identifier of the channel (e.g., `whatsapp`, `twilio_sms`, `sendgrid`).

**Body:**
- Raw payload from the provider.

**Responses:**
- `200 OK`: Event received and queued.
- `401 Unauthorized`: Invalid signature.

---

## 2. Internal Service API (Python)

These methods are available to other backend services (Agents, Workflows) via the `GatewayService` class.

### `GatewayService.send_message()`

Sends a message to a user.

```python
async def send_message(
    self, 
    session_key: str, 
    content: str, 
    attachments: List[str] = [],
    metadata: Dict = {}
) -> str:
    """
    Args:
        session_key: The target identity (e.g., 'whatsapp:+1555...').
        content: The text body of the message.
        attachments: List of URLs to media files.
        metadata: Optional channel-specific overrides (e.g., template vars).
        
    Returns:
        message_id: The provider's message ID.
    """
```

### `GatewayService.broadcast_message()`

Sends a message to multiple users.

```python
async def broadcast_message(
    self,
    session_keys: List[str],
    content: str
) -> Dict[str, str]:
    """
    Returns:
        Dict mapping session_key -> message_id.
    """
```

### `GatewayService.get_history()`

Retrieves chat history for a session (normalized).

```python
async def get_history(
    self,
    session_key: str,
    limit: int = 50,
    before_cursor: str = None
) -> List[NormalizedMessage]:
    pass
```

---

## 3. Data Models (Pydantic)

### `InboundMessage`

```python
class InboundMessage(BaseModel):
    id: str                 # Unique ID of the event
    channel_id: str         # 'whatsapp', 'sms'
    session_key: str        # 'whatsapp:+15551234'
    sender_name: str        # 'Alice Smith' (if available)
    content: str            # 'Hello world'
    attachments: List[Attachment] = []
    timestamp: datetime
    raw_payload: Dict       # Original provider payload (for debugging)
```

### `OutboundMessage`

```python
class OutboundMessage(BaseModel):
    session_key: str
    content: str
    reply_to_message_id: Optional[str] = None
    priority: str = 'normal' # 'normal', 'high'
```
