import asyncio
import os
import sys

# Ensure backend acts as root
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.gateway import GatewayService
from app.gateway.registry import PluginRegistry

async def main():
    print("🌍 Testing Universal Gateway...")
    
    # 1. Verify Registry
    print("\n[1] Checking Registry...")
    channels = PluginRegistry.list_channels()
    print(f"   Supported Channels: {channels}")
    
    if "terminal" not in channels or "email" not in channels:
        print("❌ FAIL: Plugins not registered.")
        return
        
    service = GatewayService()
    
    # 2. Test Outbound (Terminal)
    print("\n[2] Testing Outbound (Terminal)...")
    try:
        msg_id = await service.send_message("terminal:user_123", "Hello World via Gateway!")
        print(f"   ✅ Sent! ID: {msg_id}")
    except Exception as e:
        print(f"   ❌ Fail: {e}")

    # 3. Test Outbound (Email)
    print("\n[3] Testing Outbound (Email)...")
    try:
        msg_id = await service.send_message("email:alice@example.com", "Your weekly digest is here.")
        print(f"   ✅ Sent! ID: {msg_id}")
    except Exception as e:
        print(f"   ❌ Fail: {e}")

    # 4. Test Inbound (Mock Webhook)
    print("\n[4] Testing Inbound Webhook Parsing...")
    payload = {"from": "user_456", "text": "STOP"}
    result = await service.process_webhook("terminal", payload)
    
    if result and result.content == "STOP":
         print(f"   ✅ Parsed Inbound: '{result.content}' from {result.session_key}")
    else:
         print(f"   ❌ Fail: Webhook not processed correctly. Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
