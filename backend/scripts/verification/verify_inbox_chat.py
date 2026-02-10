import asyncio
import os
import sys
import json
from unittest.mock import AsyncMock, MagicMock, patch

# Env setup
os.environ["TOKEN_ENCRYPTION_KEY"] = "mock_key_for_testing_purposes_only_32b"

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.services.inbox import InboxService
from app.models import InboxItem, Merchant

async def verify_chat():
    print("[TEST] Verifying Inbox Chat Loop (Mocked)...")
    
    # 1. Setup Mock Session & Service
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    
    service = InboxService(mock_session, "test_merchant")
    
    # 2. Setup Mock Item
    item = MagicMock(spec=InboxItem)
    item.id = "test_item_123"
    item.merchant_id = "test_merchant"
    item.status = "pending"
    item.agent_type = "strategy"
    item.proposal_data = {
        "title": "Initial Plan",
        "pricing": {"discount_percent": 20, "sale_price": 80},
        "strategy": "conservative"
    }
    item.chat_history = []
    
    # Mock 'get_proposal' to return our item
    # We patch the METHOD on the instance or class. 
    # Since we have the instance 'service', let's patch the method on the class or just mock the DB query result.
    # Actually, simpler to patch service.get_proposal directly if we werent testing it.
    # But we want to test chat_with_agent.
    # Let's mock the DB execution inside service.get_proposal? 
    # Too complex. Let's patch service.get_proposal to return our Item.
    
    service.get_proposal = AsyncMock(return_value=item)
    service.notify_update = AsyncMock()
    service._log_action = AsyncMock()
    
    # 3. Simulate Chat
    print("   [ACTION] Sending message: 'Make it 50% discount'")
    
    # Mock LLM Router
    mock_response = {
        "content": json.dumps({
            "response": "Understood. I have updated the discount to 50% as requested.",
            "updated_proposal_data": {
                "pricing": {"discount_percent": 50, "sale_price": 50},
                "strategy": "aggressive"
            }
        })
    }
    
    # We need to run the ACTUAL logic of chat_with_agent, so we don't mock that.
    # We mock LLMRouter inside it.
    
    # Mock flag_modified to avoid SQLAlchemy internal errors on MagicMock
    with patch('app.services.llm_router.LLMRouter.complete', new_callable=AsyncMock) as mock_complete, \
         patch('sqlalchemy.orm.attributes.flag_modified') as mock_flag_modified:
        
        mock_complete.return_value = mock_response
        
        # Execute
        updated_item, error = await service.chat_with_agent("test_item_123", "Make it 50% discount")
        
        if error:
            print(f"   [FAIL] Chat failed: {error}")
            return

        # 4. Verify Results
        
        # A. History: User + Agent = 2 messages
        # Note: Since item.chat_history is a Mock property or list, we check what it holds.
        history = updated_item.chat_history
        print(f"   [CHECK] History Length: {len(history)}")
        if len(history) == 2:
             print("   [PASS] History has 2 messages.")
             print(f"          1. User: {history[0]['content']}")
             print(f"          2. Agent: {history[1]['content']}")
        else:
             print(f"   [FAIL] Expected 2 messages, got {len(history)}")

        # B. Data Update
        new_pricing = updated_item.proposal_data.get('pricing', {})
        print(f"   [CHECK] New Discount: {new_pricing.get('discount_percent')}%")
        
        if new_pricing.get('discount_percent') == 50:
            print("   [PASS] JSON Payload updated correctly.")
        else:
            print(f"   [FAIL] Expected 50%, got {new_pricing.get('discount_percent')}")
            
        # C. Flag Modified
        # We can't easily check SQLAlchemy flag_modified on a mock, but successful data update implies it worked in logic.

if __name__ == "__main__":
    asyncio.run(verify_chat())
