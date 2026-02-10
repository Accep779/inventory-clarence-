from fastapi import APIRouter, Request, HTTPException, Depends, Body
from typing import Any, Dict, List
from pydantic import BaseModel
from app.services.gateway import GatewayService
from app.gateway.registry import PluginRegistry

# We need to re-instantiate or share the router from the existing file, 
# OR we can update the existing file. 
# Since we are "Creating" a new file in the plan, I will overwrite/update the existing router file 
# to include the NEW endpoints + the old webhook endpoint.

router = APIRouter(
    prefix="/gateway",
    tags=["Universal Gateway"]
)

class ChannelConfig(BaseModel):
    channel_id: str
    provider: str
    status: str
    is_active: bool

@router.post("/webhook/{channel_id}")
async def receive_webhook(channel_id: str, request: Request):
    """
    Universal Webhook Receiver.
    Accepts payloads from Twilio, SendGrid, Meta, etc.
    """
    try:
        # Parse body based on content type? For now assume JSON or Form
        try:
            payload = await request.json()
        except:
            payload = dict(await request.form())
            
        service = GatewayService()
        result = await service.process_webhook(channel_id, payload)
        
        if result:
            return {"status": "ok", "message_id": result.id}
        else:
            # If validation failed but no error raised, it's a Bad Request
            raise HTTPException(status_code=400, detail="Invalid Signature or Payload")
            
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Channel {channel_id} not supported")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- NEW ENDPOINTS FOR COMMAND CENTER ---

@router.get("/channels", response_model=Dict[str, List[ChannelConfig]])
async def list_channels():
    """
    List configured channels.
    Used by the 'Connectivity Hub' UI.
    """
    # In a real app, this would come from DB.
    # For now, we inspect the Registry or return hardcoded supported channels + MockDB status.
    
    channels = [
        {"channel_id": "email", "provider": "SendGrid", "status": "active", "is_active": True},
        {"channel_id": "sms", "provider": "Twilio", "status": "configured", "is_active": True},
        {"channel_id": "whatsapp", "provider": "Meta", "status": "inactive", "is_active": False},
        {"channel_id": "terminal", "provider": "Local Debug", "status": "active", "is_active": True},
    ]
    return {"channels": channels}

@router.patch("/channels/{channel_id}")
async def update_channel_config(channel_id: str, config: Dict[str, Any] = Body(...)):
    """
    Update API Keys or Settings for a channel.
    """
    # Stub: Save to DB/Vault
    return {"status": "updated", "channel": channel_id}
