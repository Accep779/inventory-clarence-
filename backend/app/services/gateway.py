from app.gateway.registry import PluginRegistry
from app.gateway.protocol import InboundMessage
from typing import Dict, Any, List
# Import known plugins to ensure registration
import app.channels.terminal
import app.channels.email

class GatewayService:
    """
    The Universal Gateway Service.
    
    Agents use this to talk to the world.
    """
    
    def __init__(self):
        self.registry = PluginRegistry()

    async def send_message(self, session_key: str, content: str, priority: str = "normal", **kwargs) -> str:
        """
        Route an outbound message to the correct plugin.
        
        Args:
            session_key: e.g. 'whatsapp:123', 'email:bob@co.com'
            content: The text body
            priority: 'low', 'normal', 'high'. 'low' messages are batched.
        """
        # [ANTI-FATIGUE]: Intercept low-priority messages
        if priority == "low":
            from app.services.digest import DigestService
            # Extract merchant_id / topic from context or default
            merchant_id = kwargs.get("merchant_id", "unknown_merchant") 
            topic = kwargs.get("topic", "general")
            
            digest = DigestService()
            await digest.add_notification(merchant_id, content, priority, topic)
            return "queued_for_digest"

        if ":" not in session_key:
             # Default to terminal if malformed (for dev safety)
             plugin_id = "terminal"
             clean_key = session_key
        else:
            plugin_id, clean_key = session_key.split(":", 1)
        
        try:
            plugin = self.registry.get(plugin_id)
            msg_id = await plugin.send_message(clean_key, content, **kwargs)
            return msg_id
        except ValueError as e:
            print(f"❌ [Gateway] Routing Error: {e}")
            raise
    
    async def process_webhook(self, channel_id: str, payload: Dict[str, Any]):
        """
        Handle Inbound Webhook -> Normalize -> Emit Event.
        """
        try:
            plugin = self.registry.get(channel_id)
            message = await plugin.validate_webhook(payload)
            
            if message:
                print(f"📥 [Gateway] Inbound from {message.session_key}: {message.content}")
                # TODO: Push to Redis Event Bus here
                # await self.event_bus.publish("gateway.message_received", message)
                return message
            else:
                print(f"⚠️ [Gateway] Invalid webhook for {channel_id}")
                return None
        except Exception as e:
            print(f"❌ [Gateway] Webhook Error: {e}")
            return None
