import asyncio
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

# Mock Environment BEFORE imports
os.environ["TOKEN_ENCRYPTION_KEY"] = "mock_key_for_testing_purposes_only_32b"

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.agents.execution import ExecutionAgent
from app.models import Merchant, InboxItem

async def test_ciba_policy():
    print("[TEST] Verifying Execution CIBA Policy...")
    
    agent = ExecutionAgent("test_merchant")
    start_time = datetime.utcnow()
    
    # Scenario 1: High Discount (Should Trigger)
    mock_session = MagicMock()
    mock_execute = AsyncMock()
    mock_execute.scalar_one_or_none = MagicMock()
    mock_session.execute = mock_execute
    
    # Mock Context
    merchant = MagicMock(spec=Merchant)
    merchant.max_auto_discount = 0.40 # 40%
    merchant.created_at = start_time - timedelta(days=100) # Old merchant
    
    proposal = MagicMock(spec=InboxItem)
    proposal.proposal_data = {"discount": "50%"} # 50% > 40%
    
    # Setup Returns
    mock_execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: proposal), # 1st call: proposal
        MagicMock(scalar_one_or_none=lambda: merchant)  # 2nd call: merchant
    ]
    
    # Patch async_session_maker
    from unittest.mock import patch
    with patch('app.agents.execution.async_session_maker') as mock_asm:
        mock_asm.return_value.__aenter__.return_value = mock_session
        
        result = await agent._requires_async_auth("prop_1", {"estimated_cost": 100})
        
        if result is True:
            print("   [PASS]: High Discount (50%) triggered CIBA.")
        else:
            print("   [FAIL]: High Discount did NOT trigger CIBA.")

    # Scenario 2: High Budget (Should Trigger)
    mock_execute.side_effect = [
        MagicMock(scalar_one_or_none=lambda: MagicMock(proposal_data={"discount": "10%"})),
        MagicMock(scalar_one_or_none=lambda: merchant)
    ]
    with patch('app.agents.execution.async_session_maker') as mock_asm:
        mock_asm.return_value.__aenter__.return_value = mock_session
        result = await agent._requires_async_auth("prop_2", {"estimated_cost": 600}) # 600 > 500
        
        if result is True:
            print("   [PASS]: High Budget ($600) triggered CIBA.")
        else:
            print("   [FAIL]: High Budget did NOT trigger CIBA.")

if __name__ == "__main__":
    asyncio.run(test_ciba_policy())
