import pytest
import asyncio
import time
import random
import logging
import psutil
import os
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from decimal import Decimal


# --- PRE-IMPORT MOCKING ---
class StatefulRedisMock:
    def __init__(self):
        self.data = {}
    def get(self, key): return self.data.get(key)
    def set(self, key, value):
        self.data[key] = str(value)
        return True
    def setex(self, key, time, value):
        self.data[key] = str(value)
        return True
    def incr(self, key):
        val = int(self.data.get(key, 0)) + 1
        self.data[key] = str(val)
        return val
    def delete(self, *keys):
        for k in keys: self.data.pop(k, None)
        return True
    def expire(self, key, seconds): return True
    def exists(self, key): return key in self.data

# Mock Database Models
mock_merchant = MagicMock()
mock_merchant.id = "storm_merchant"
mock_merchant.access_token = "mock_token"
mock_merchant.shopify_domain = "test.myshopify.com"
mock_merchant.sync_status = "synced"
mock_merchant.max_auto_discount = Decimal("0.40")
mock_merchant.max_auto_ad_spend = Decimal("500.00")
mock_merchant.governor_calibration_threshold = 50
mock_merchant.governor_trust_threshold = Decimal("0.95")
mock_merchant.governor_aggressive_mode = False


mock_variant = MagicMock()
mock_variant.price = 50.0
mock_variant.sku = "storm_sku_123"

mock_product = MagicMock()
mock_product.id = "storm_product_123"
mock_product.merchant_id = "storm_merchant"
mock_product.title = "Storm Product"
mock_product.is_dead_stock = True
mock_product.dead_stock_severity = "high"
mock_product.total_inventory = 100
mock_product.units_sold_30d = 5
mock_product.cost_per_unit = Decimal("25.00")
mock_product.velocity_score = Decimal("0.1")
mock_product.variants = [mock_variant]

mock_item = MagicMock()
mock_item.id = "storm_proposal_123"
mock_item.merchant_id = "storm_merchant"
mock_item.type = "clearance_proposal"
mock_item.status = "pending"
mock_item.proposal_data = {}
mock_item.confidence = 0.85
mock_item.created_at = datetime.utcnow()




def create_mock_result(val):
    res = MagicMock()
    res.scalar_one_or_none.return_value = val
    res.scalars.return_value.all.return_value = [val] if val else []
    res.scalar.return_value = val
    return res

async def mock_execute(stmt, *args, **kwargs):
    stmt_str = str(stmt).lower()
    print(f"DEBUG SQL: {stmt_str}") 
    
    # Specific table matches first
    if "merchant_journey" in stmt_str: return create_mock_result([])
    if "from products" in stmt_str: return create_mock_result(mock_product)
    if "from product_variants" in stmt_str: return create_mock_result(mock_variant)
    if "from inbox_items" in stmt_str: return create_mock_result(mock_item)
    if "from customers" in stmt_str: return create_mock_result([]) # Default empty for customers list
    if "from merchants" in stmt_str: return create_mock_result(mock_merchant)

    # Fallbacks for counts/scalar checks
    if "count" in stmt_str and "from customers" in stmt_str: return create_mock_result(100)
    if "governor_risk_policies" in stmt_str: return create_mock_result([]) # No specific policies
    if "governor" in stmt_str: return create_mock_result(MagicMock(trust_score=0.9)) # Fallback
    
    return create_mock_result(None)


async def mock_get(model, id, **kwargs):
    model_str = str(model).lower()
    if "merchant" in model_str: return mock_merchant
    if "product" in model_str: return mock_product
    if "inbox" in model_str: return mock_item
    return None

mock_session = AsyncMock()
mock_session.execute.side_effect = mock_execute
mock_session.get.side_effect = mock_get
mock_session.scalar.side_effect = lambda stmt, *args, **kwargs: 100 if "count" in str(stmt).lower() else None
mock_session.add = MagicMock()
mock_session.merge = MagicMock()
mock_session.refresh = AsyncMock()
mock_session.flush = AsyncMock()
mock_session.commit = AsyncMock()
mock_session.rollback = AsyncMock()
mock_session.close = AsyncMock()


# Global redis instance
mock_redis_instance = StatefulRedisMock()

# 1. Apply patches BEFORE app imports
patch("app.redis.get_redis_client", return_value=mock_redis_instance).start()
patch("app.middleware.idempotency.get_redis_client", return_value=mock_redis_instance).start()
patch("app.database.async_session_maker", return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_session))).start()

# 2. Patch LLM Router and Claude API
mock_router = AsyncMock()
mock_router.complete.return_value = {"content": '{"conservative": {"strategy": "flash_sale"}, "balanced": {"strategy": "flash_sale"}, "aggressive": {"strategy": "flash_sale"}, "recommended_strategy": "flash_sale", "reflection": "Good", "approval": true, "concerns": [], "suggestion": "proceed", "confidence": 0.9, "email_subject": "Sale", "email_preview": "Sale", "email_body": "Sale", "sms_message": "Sale"}'}
patch("app.services.llm_router.LLMRouter", return_value=mock_router).start()
patch("app.services.claude_api.claude.generate", side_effect=AsyncMock(return_value="Mock response")).start()

# Bypass complex Strategy logic
patch("app.agents.strategy.StrategyAgent._calculate_pricing", side_effect=AsyncMock(return_value={
    "original_price": 50.0,
    "sale_price": 40.0,
    "discount_percent": 20.0,
    "margin_percent": 30.0,
    "cost": 25.0,
    "floor_source": "default",
    "can_liquidate": True
})).start()

patch("app.agents.strategy.StrategyAgent._get_target_audience", side_effect=AsyncMock(return_value={
    "segments": ["loyal"],
    "total_customers": 100,
    "reasoning": "Mock"
})).start()

patch("app.agents.strategy.StrategyAgent._calculate_projections", return_value={
    "conversions": 5,
    "units_cleared": 5,
    "revenue": 200.0,
    "conversion_rate": 0.05,
    "audience_size": 100
}).start()

patch("app.agents.strategy.StrategyAgent._requires_merchant_approval", return_value=True).start()




# 3. Import app and override dependencies
from app.main import app
from app.auth_middleware import get_current_tenant
from app.database import get_db
from app.config import get_settings
from app.integrations.circuit_breaker import get_klaviyo_circuit_breaker, CircuitState
from tests.chaos.chaos_hub import ChaosHub

app.dependency_overrides[get_current_tenant] = lambda: "storm_merchant"
app.dependency_overrides[get_db] = lambda: mock_session





# --- END PRE-IMPORT MOCKING ---

# Configure logging for chaos test
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chaos_storm")

settings = get_settings()


CHAOS_CONFIG = {
    "load": {
        "users": 5,
        "spawn_rate": 1,
        "duration": 600  # 10m full run
    },
    "failures": {
        "klaviyo_failure_rate": 0.5,
        "database_latency_ms": 200,
        "redis_connection_drops": True,
        "anthropic_timeout_rate": 0.3
    }
}

class StormMetrics:
    def __init__(self):
        self.total_requests = 0
        self.errors = 0
        self.latencies = []
        self.start_time = time.time()
        self.initial_memory = psutil.Process(os.getpid()).memory_info().rss
        self.final_memory = 0
        self.fallback_triggers = 0
        self.idempotency_hits = 0

def mock_redis_for_app():
    mock = StatefulRedisMock()
    with patch("app.redis.get_redis_client", return_value=mock):
        with patch("app.middleware.idempotency.get_redis_client", return_value=mock):
            yield mock

metrics = StormMetrics()

async def simulate_user_journey(user_id: int, duration: int):
    """
    Simulates a merchant journey: 
    1. Scan products
    2. Generate Strategy
    3. Approve Strategy
    4. Trigger Campaign (Klaviyo)
    """
    from httpx import ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Generate a fake merchant ID for this user session
        merchant_id = f"storm_merchant_{user_id % 10}" 
        headers = {"X-Merchant-ID": merchant_id, "Authorization": f"Bearer storm_token_{user_id}"}
        
        while time.time() - metrics.start_time < duration:
            try:
                # 1. Start Scan
                t0 = time.time()
                resp = await client.post("/api/scan/start", headers=headers)
                print(f"DEBUG: Scan Status={resp.status_code}, Body={resp.text[:100]}")
                metrics.total_requests += 1
                if resp.status_code >= 400 and resp.status_code != 429:
                    metrics.errors += 1
                metrics.latencies.append(time.time() - t0)

                # 2. Plan Strategy
                t0 = time.time()
                resp = await client.post("/api/strategy/plan", json={"product_id": "storm_product_123"}, headers=headers)
                print(f"DEBUG: Strategy Status={resp.status_code}, Body={resp.text[:100]}")
                metrics.total_requests += 1
                if resp.status_code >= 400 and resp.status_code != 429:
                    metrics.errors += 1
                metrics.latencies.append(time.time() - t0)
                
                if resp.status_code == 200:
                    # 3. Approve Strategy (Idempotency Check)
                    item_id = "storm_proposal_123"
                    idempotency_key = f"storm_key_{user_id}_{int(time.time())}"
                    t0 = time.time()
                    resp = await client.post(
                        f"/api/inbox/{item_id}/approve", 
                        headers={**headers, "Idempotency-Key": idempotency_key}
                    )
                    print(f"DEBUG: Approve Status={resp.status_code}, Body={resp.text[:100]}")
                    metrics.total_requests += 1
                    if resp.status_code >= 400 and resp.status_code != 429:
                        metrics.errors += 1
                    elif resp.status_code == 200 and resp.json().get("cached"):
                            metrics.idempotency_hits += 1
                    metrics.latencies.append(time.time() - t0)



                # Random sleep to simulate human behavior
                await asyncio.sleep(random.uniform(1, 5))
                
            except Exception as e:
                metrics.errors += 1
                logger.error(f"User {user_id} encountered error: {e}")
                await asyncio.sleep(1)


@pytest.mark.asyncio
async def test_the_perfect_storm():
    """Main Chaos Simulation."""
    logger.info("⚡ Starting The Perfect Storm Chaos Test...")
    
    hub = ChaosHub(CHAOS_CONFIG)
    hub.start()
    
    # Manually wrap our mock_redis so hub can inject drops into it
    hub._wrap_redis_client(mock_redis_instance)
    
    try:

        tasks = []
        # Spawn users
        for i in range(CHAOS_CONFIG["load"]["users"]):
            tasks.append(asyncio.create_task(simulate_user_journey(i, CHAOS_CONFIG["load"]["duration"])))
            if i % CHAOS_CONFIG["load"]["spawn_rate"] == 0:
                await asyncio.sleep(1) # Ramping up
        
        logger.info(f"🚀 {CHAOS_CONFIG['load']['users']} users spawned. Running for {CHAOS_CONFIG['load']['duration']}s...")
        
        # Periodic status logging
        for _ in range(int(CHAOS_CONFIG["load"]["duration"] / 30)):
            await asyncio.sleep(30)
            elapsed = time.time() - metrics.start_time
            current_error_rate = (metrics.errors / metrics.total_requests * 100) if metrics.total_requests > 0 else 0
            logger.info(f"📊 Progress: {elapsed:.0f}s | Requests: {metrics.total_requests} | Errors: {metrics.errors} ({current_error_rate:.2f}%)")
            
            # Check Circuit Breaker
            try:
                klaviyo = get_klaviyo_circuit_breaker()
                status = klaviyo.get_status()
                logger.info(f"🔌 Circuit Breaker (Klaviyo): {status['state']}")
            except Exception as e:
                logger.warning(f"Could not fetch CB status (intended drop?): {e}")

        # Wait for all journeys to complete, ignoring exceptions from individual tasks
        # as they should be caught within the task itself, but just in case
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"⚠️ A user journey task failed with unhandled error: {r}")

        
    finally:
        hub.stop()
        metrics.final_memory = psutil.Process(os.getpid()).memory_info().rss
        
    logger.info("🏁 Chaos Test Complete. Analyzing Results...")
    
    # Validation Logic
    error_rate = metrics.errors / metrics.total_requests if metrics.total_requests > 0 else 1.0
    logger.info(f"Final Error Rate: {error_rate * 100:.2f}%")
    
    # 1. Check error rate < 5%
    # Note: In a true chaos storm with 50% external failures, 
    # the SYSTEM error rate should be low because of circuit breakers and fallbacks.
    assert error_rate < 0.05 
    
    # 2. Check circuit breaker state (should have opened and potentially half-opened)
    # Since we can't easily check history here, we just check current state or hub metrics
    assert hub.metrics["klaviyo_failures"] > 5
    
    # 3. Check Memory Leak
    memory_growth = (metrics.final_memory / metrics.initial_memory) - 1
    logger.info(f"Memory Growth: {memory_growth * 100:.2f}%")
    assert memory_growth < 0.20
    
    # Produce metrics for reporting
    from tests.chaos.generate_report import generate_markdown_report
    generate_markdown_report(metrics, hub)
