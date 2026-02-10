import asyncio
import sys
import os
import json
import time

# Mock Environment BEFORE imports
os.environ["TOKEN_ENCRYPTION_KEY"] = "mock_key_for_testing_purposes_only_32b"
# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.services.clustering import InventoryClusteringService

# Mock Redis
class MockRedis:
    def __init__(self):
        self.store = {}
    def get(self, key):
        return self.store.get(key)
    def setex(self, key, ttl, value):
        self.store[key] = value

async def test_clustering_cache():
    print("[TEST] Verifying Observer Clustering Cache...")
    
    # Use patch to prevent getting a real Redis client on init AND real Model load
    from unittest.mock import patch, MagicMock
    import numpy as np
    
    # Mock Embedding Model
    mock_model = MagicMock()
    # Return random embeddings of shape (N, 384)
    mock_model.encode.side_effect = lambda texts: np.random.rand(len(texts), 384)

    with patch('app.services.clustering.get_redis_client') as mock_get_redis, \
         patch('app.services.clustering.SentenceTransformer', return_value=mock_model):
        
        mock_redis_instance = MockRedis()
        mock_get_redis.return_value = mock_redis_instance
        
        # Setup
        service = InventoryClusteringService("test_merchant")
        # Ensure our mock is used (though patch should have handled it)
        service.redis = mock_redis_instance 
        
        products = [
            {"id": 1, "title": "Blue Jeans", "price": 50, "inventory": 100, "product_type": "Pants"},
            {"id": 2, "title": "Blue Shirt", "price": 40, "inventory": 50, "product_type": "Shirt"},
            {"id": 3, "title": "Red Dress", "price": 80, "inventory": 20, "product_type": "Dress"}
        ] * 10 # 30 products
        
        # Run 1 (Cold)
        start_time = time.time()
        res1 = await service.cluster_inventory(products, n_clusters=2)
        t1 = time.time() - start_time
        print(f"   Run 1 (Cold): {t1:.4f}s")
        
        # Run 2 (Warm)
        start_time = time.time()
        res2 = await service.cluster_inventory(products, n_clusters=2)
        t2 = time.time() - start_time
        print(f"   Run 2 (Warm): {t2:.4f}s")
        
        # Assertions
        if t2 < (t1 * 0.1): # Should be at least 10x faster
            print("   [PASS]: Cache logic detected (Run 2 was instant).")
        else:
            print("   [FAIL]: Cache did not significantly speed up execution.")
            
        if json.dumps(res1) == json.dumps(res2):
            print("   [PASS]: Results match exactly.")
        else:
            print("   [FAIL]: Results differ.")

if __name__ == "__main__":
    asyncio.run(test_clustering_cache())
