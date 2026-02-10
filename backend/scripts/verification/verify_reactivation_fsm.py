import asyncio
import sys
import os
import json
from unittest.mock import MagicMock, AsyncMock, patch

# Mock Environment BEFORE imports
os.environ["TOKEN_ENCRYPTION_KEY"] = "mock_key_for_testing_purposes_only_32b"

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.agents.reactivation import ReactivationAgent
from app.models import Customer, CommercialJourney

async def test_reactivation_fsm():
    print("[TEST] Verifying Reactivation State Machine...")
    
    agent = ReactivationAgent("test_merchant")
    
    # Mock Customer
    customer = MagicMock(spec=Customer)
    customer.sms_optin = False
    customer.email_optin = True
    customer.rfm_segment = "at_risk"
    customer.first_name = "John"
    
    # Mock Journey at Step 1 (Day 0)
    journey = MagicMock(spec=CommercialJourney)
    journey.current_touch = 0 # 0 means we are ABOUT to do Step 1
    
    # We need to mock the LLM router to just return success
    mock_router = MagicMock()
    mock_router.complete = AsyncMock(return_value={
        "content": json.dumps({"body": "mock", "subject": "mock"})
    })
    agent.router = mock_router
    
    # Mock DNA
    # Patch the SERVICE definition, so the local import picks up the mock
    with patch('app.services.dna.DNAService') as mock_dna_cls:
        mock_dna = AsyncMock()
        mock_dna.get_dna = AsyncMock(return_value=None)
        mock_dna_cls.return_value = mock_dna

        # Test Step 1
        print("   Testing Step 1 -> 2...")
        res = await agent._reason_about_next_touch(customer, journey, [])
        if res.get('channel') == 'email' and res.get('terminate') is False:
             print("   [PASS]: Step 1 = Email")
        else:
             print(f"   [FAIL]: Step 1 expected Email, got {res}")

        # Test Step 3 -> Terminate
        print("   Testing Step 3 -> Terminate...")
        journey.current_touch = 3
        res = await agent._reason_about_next_touch(customer, journey, [])
        if res.get('terminate') is True:
             print("   [PASS]: Step 4 (Index 3+1) triggered Termination.")
        else:
             print(f"   [FAIL]: Expected termination, got {res}")

if __name__ == "__main__":
    asyncio.run(test_reactivation_fsm())
