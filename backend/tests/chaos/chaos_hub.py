import random
import asyncio
import logging
from unittest.mock import patch, MagicMock, AsyncMock
import requests
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)

class ChaosHub:
    """
    Central control for injecting chaos into the system.
    """
    def __init__(self, config: dict):
        self.config = config
        self.patches = []
        self.active = False
        self.metrics = {
            "klaviyo_failures": 0,
            "db_latency_injected": 0,
            "redis_drops": 0,
            "anthropic_timeouts": 0
        }

    def start(self):
        """Begin monkeypatching services."""
        self.active = True
        
        # 1. Klaviyo Failure Injection
        self._patch_klaviyo()
        
        # 2. Database Latency Injection
        self._patch_database()
        
        # 3. Redis Connection Drops
        self._patch_redis()
        
        # 4. Anthropic Timeout Injection
        self._patch_anthropic()

    def stop(self):
        """Remove all patches."""
        self.active = False
        for p in self.patches:
            p.stop()
        self.patches = []

    def _patch_klaviyo(self):
        """Intercept requests.post to Klaviyo."""
        original_post = requests.post
        
        def chaotic_post(url, *args, **kwargs):
            if "klaviyo.com" in url and random.random() < self.config["failures"]["klaviyo_failure_rate"]:
                self.metrics["klaviyo_failures"] += 1
                mock_resp = MagicMock()
                mock_resp.status_code = 500
                mock_resp.text = "Chaos Hub: Simulated Klaviyo Failure"
                return mock_resp
            return original_post(url, *args, **kwargs)
            
        p = patch("requests.post", side_effect=chaotic_post)
        p.start()
        self.patches.append(p)

    def _patch_database(self):
        """Inject latency into SQLAlchemy async executions."""
        from sqlalchemy.ext.asyncio import AsyncSession
        
        original_execute = AsyncSession.execute
        
        async def chaotic_execute(self_session, statement, *args, **kwargs):
            if self.active:
                latency = self.config["failures"]["database_latency_ms"] / 1000.0
                await asyncio.sleep(latency)
            return await original_execute(self_session, statement, *args, **kwargs)
            
        p = patch("sqlalchemy.ext.asyncio.AsyncSession.execute", side_effect=chaotic_execute, autospec=True)
        p.start()
        self.patches.append(p)

    def _patch_redis(self):
        """Simulate Redis connection drops by patching redis methods."""
        import redis
        
        # 1. Patch the global redis.from_url for any internal uses
        original_from_url = redis.from_url
        def chaotic_from_url(*args, **kwargs):
            client = original_from_url(*args, **kwargs)
            self._wrap_redis_client(client)
            return client
        p1 = patch("redis.from_url", side_effect=chaotic_from_url)
        p1.start()
        self.patches.append(p1)

        # 2. Also patch app.redis.get_redis_client's return value directly if possible
        # This is more robust for when get_redis_client is already mocked in tests
        try:
             from app.redis import get_redis_client
             # If it's already a mock, we can't easily patch it globally without re-mocking
             # But we can try to patch the specific methods on the mock instance
        except ImportError:
             pass

    def _wrap_redis_client(self, client):
        """Inject failure logic into a redis client instance."""
        import redis
        original_get = client.get
        
        def chaotic_get(key):
            if self.active and self.config["failures"]["redis_connection_drops"] and random.random() < 0.1:
                self.metrics["redis_drops"] += 1
                raise redis.ConnectionError("Chaos Hub: Redis Drop")
            return original_get(key)
            
        client.get = chaotic_get
        # Also patch set and setex if used
        if hasattr(client, 'set'):
            original_set = client.set
            client.set = lambda *a, **k: (self.metrics.update({"redis_drops": self.metrics["redis_drops"]+1}), 
                                         exec('raise(redis.ConnectionError("Chaos Hub: Redis Drop"))'))[1] \
                                         if (self.active and self.config["failures"]["redis_connection_drops"] and random.random() < 0.1) \
                                         else original_set(*a, **k)


    def _patch_anthropic(self):
        """Simulate Anthropic timeouts."""
        from anthropic.resources import AsyncMessages
        
        original_create = AsyncMessages.create
        
        async def chaotic_create(self_res, *args, **kwargs):
            if self.active and random.random() < self.config["failures"]["anthropic_timeout_rate"]:
                self.metrics["anthropic_timeouts"] += 1
                logger.warning("Chaos Hub: Injecting Anthropic Timeout")
                # Simulate timeout by sleeping longer than expected
                await asyncio.sleep(10) 
                raise asyncio.TimeoutError("Chaos Hub: Anthropic Timeout")
            return await original_create(self_res, *args, **kwargs)
            
        p = patch("anthropic.resources.AsyncMessages.create", side_effect=chaotic_create, autospec=True)
        p.start()
        self.patches.append(p)
# We might need to patch AsyncAnthropic instance methods
