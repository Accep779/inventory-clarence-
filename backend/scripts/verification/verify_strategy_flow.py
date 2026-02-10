import asyncio
import sys
import os
import json
from unittest.mock import AsyncMock, MagicMock

# Mock Environment BEFORE imports
os.environ["TOKEN_ENCRYPTION_KEY"] = "mock_key_for_testing_purposes_only_32b"

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.agents.strategy import StrategyAgent
from app.models import Product, ProductVariant

async def test_strategy_parallelism():
    print("[TEST] Verifying Strategy Parallelism & Critic...")
    
    agent = StrategyAgent("test_merchant")
    
    # Mock LLM Router to track calls
    agent._generate_plan_variation = AsyncMock(return_value={
        "strategy": "progressive_discount",
        "reasoning": "Mock plan"
    })
    
    # Mock Critic to REJECT first, then ACCEPT or just return result
    mock_router = MagicMock()
    mock_router.complete = AsyncMock(return_value={
        "content": json.dumps({
            "recommended_strategy": "progressive_discount", 
            "reflection": "Chosen for safety."
        })
    })
    
    # Mock Dependencies
    mock_session = MagicMock()
    # execute must be async
    mock_execute = AsyncMock()
    mock_session.execute = mock_execute
    # Result setup
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [] # No active journeys
    mock_execute.return_value = mock_result

    mock_memory = MagicMock()
    mock_memory.get_merchant_preferences = AsyncMock(return_value={"max_auto_discount": 0.40})
    mock_memory.recall_campaign_outcomes = AsyncMock(return_value=[])
    
    # Mock Product
    product = MagicMock(spec=Product)
    product.id = "p1"
    product.title = "Test Product"
    product.dead_stock_severity = "high"
    product.variants = [MagicMock(spec=ProductVariant, price=100)]
    product.cost_per_unit = 50
    
    # Run
    try:
        # Patch the MODULES where the classes are defined
        from unittest.mock import patch
        
        # We need to ensure MemoryService is also mocked if it's instantiated
        with patch('app.services.llm_router.LLMRouter', return_value=mock_router), \
             patch('app.services.global_brain.GlobalBrainService') as mock_gb, \
             patch('app.services.dna.DNAService') as mock_dna, \
             patch('app.services.memory.MemoryService', return_value=mock_memory):
                 
            mock_gb.get_applicable_patterns = AsyncMock(return_value=[])
            mock_dna_instance = AsyncMock()
            mock_dna_instance.get_merchant_dna = AsyncMock(return_value=None)
            mock_dna.return_value = mock_dna_instance
            
            res = await agent._select_multi_plan_strategy(product, mock_session)
            
            # Assertions
            print(f"   Result Strategy: {res['recommended_strategy']}")
            
            # Verify Parallelism: _generate_plan_variation called 3 times?
            call_count = agent._generate_plan_variation.call_count
            print(f"   Plan Variations Generated: {call_count}")
            
            if call_count == 3:
                print("   [PASS]: Parallel generation confirmed (3 calls).")
            else:
                print(f"   [FAIL]: Expected 3 distinct generations, got {call_count}.")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"   [FAIL]: Execution error: {e}")

if __name__ == "__main__":
    asyncio.run(test_strategy_parallelism())
