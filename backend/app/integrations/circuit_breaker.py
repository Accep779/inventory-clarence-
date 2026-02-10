# backend/app/integrations/circuit_breaker.py
"""
Circuit Breaker Pattern Implementation.

Protects against cascading failures when external services (Klaviyo, Twilio) are down.
Uses Redis for distributed state across workers.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Failing, requests rejected immediately
- HALF_OPEN: Testing recovery with limited requests
"""

from enum import Enum
from datetime import datetime, timedelta
import logging
import httpx
import json
import asyncio
from typing import Callable, Any, Optional, Dict

from app.redis import get_redis_client
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject immediately  
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejecting calls."""
    
    def __init__(self, service_name: str, retry_after: int = 60):
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"{service_name} circuit breaker is OPEN. "
            f"Service experiencing issues. Try again in {retry_after}s"
        )


class CircuitBreaker:
    """
    Distributed circuit breaker using Redis for state.
    
    Usage:
        breaker = CircuitBreaker("klaviyo")
        result = await breaker.call(api_function, arg1, arg2)
    """
    
    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_max_calls: int = 3
    ):
        """
        Initialize circuit breaker.
        
        Args:
            service_name: Name of the external service (klaviyo, twilio)
            failure_threshold: Number of failures before opening circuit
            timeout_seconds: Time to wait before attempting recovery
            half_open_max_calls: Number of test calls allowed in half-open state
        """
        self.redis = get_redis_client()
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.timeout = timeout_seconds
        self.half_open_max_calls = half_open_max_calls
        
        # Redis keys
        self.key_state = f"circuit_breaker:{service_name}:state"
        self.key_failures = f"circuit_breaker:{service_name}:failures"
        self.key_last_failure = f"circuit_breaker:{service_name}:last_failure"
        self.key_half_open_calls = f"circuit_breaker:{service_name}:half_open_calls"
        self.key_timeout_multiplier = f"circuit_breaker:{service_name}:timeout_multiplier"
    
    async def _send_slack_alert(self, message: str, level: str = "warning"):
        """Send alert to Slack channel."""
        if not settings.SLACK_WEBHOOK_URL:
            logger.info(f"Slack alert (skipped - no webhook): {message}")
            return
            
        color = "#ff0000" if level == "error" else "#36a64f"
        payload = {
            "channel": settings.SLACK_ALERTS_CHANNEL,
            "attachments": [{
                "fallback": message,
                "color": color,
                "title": f"Circuit Breaker Alert: {self.service_name.upper()}",
                "text": message,
                "footer": "Cephly Safety Engine",
                "ts": datetime.utcnow().timestamp()
            }]
        }
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(settings.SLACK_WEBHOOK_URL, json=payload, timeout=5.0)
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
    
    async def call(self, func: Callable, *args, merchant_id: Optional[str] = None, db: Optional[Any] = None, **kwargs) -> Any:
        # Note: Any for db to avoid typed circular import if possible
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to execute
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Result from function
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        state = self._get_state()
        
        if state == CircuitState.OPEN:
            if self._should_attempt_reset():
                await self._transition_to_half_open()
            else:
                retry_after = self._get_retry_seconds()
                logger.warning(f"Circuit breaker OPEN for {self.service_name}, rejecting call")
                
                # If we have a merchant ID and DB session, we can log this specific failure
                if merchant_id and db:
                    await self._create_degradation_inbox_item(merchant_id, db, retry_after)
                
                raise CircuitBreakerOpenError(self.service_name, retry_after)
        
        if state == CircuitState.HALF_OPEN:
            if not await self._can_attempt_half_open_call():
                raise CircuitBreakerOpenError(self.service_name, self.timeout)
        
        # Attempt the call
        try:
            result = await func(*args, **kwargs)
            await self._record_success()
            return result
        except Exception as e:
            await self._record_failure(e, merchant_id, db)
            raise
    
    def _get_state(self) -> CircuitState:
        """Fetch current state from Redis."""
        state = self.redis.get(self.key_state)
        if state:
            return CircuitState(state)
        return CircuitState.CLOSED
    
    async def _record_success(self):
        """Reset failure count, transition to CLOSED if in HALF_OPEN."""
        state = self._get_state()
        
        # Reset all failure tracking
        self.redis.delete(self.key_failures)
        self.redis.delete(self.key_last_failure)
        self.redis.delete(self.key_half_open_calls)
        
        if state == CircuitState.HALF_OPEN:
            # Reset exponential backoff multiplier on full recovery
            self.redis.delete(self.key_timeout_multiplier)
            self.redis.set(self.key_state, CircuitState.CLOSED.value)
            logger.info(f"Circuit breaker CLOSED for {self.service_name} - service recovered")
            asyncio.create_task(self._send_slack_alert(f"Service {self.service_name} has recovered. Circuit is now CLOSED.", "info"))
    
    async def _record_failure(self, error: Exception, merchant_id: Optional[str] = None, db: Optional[Any] = None):
        """Increment failure count, transition to OPEN if threshold exceeded."""
        # Only count server errors and timeouts
        if not self._is_circuit_breaker_error(error):
            return
        
        # Increment failure count
        failures = self.redis.incr(self.key_failures)
        self.redis.set(self.key_last_failure, datetime.utcnow().isoformat())
        
        logger.warning(f"Circuit breaker recorded failure {failures}/{self.failure_threshold} for {self.service_name}: {error}")
        
        if failures >= self.failure_threshold:
            await self._transition_to_open(merchant_id, db)
    
    def _is_circuit_breaker_error(self, error: Exception) -> bool:
        """
        Determine if error should count toward circuit breaker.
        
        Counts: Timeouts, connection errors, 5xx errors, rate limits
        Ignores: 4xx client errors, validation errors
        """
        error_name = type(error).__name__.lower()
        error_msg = str(error).lower()
        
        # Count these errors
        if any(term in error_name for term in ['timeout', 'connection', 'network']):
            return True
        if any(term in error_msg for term in ['timeout', 'connection', 'rate limit', '503', '502', '500', '429']):
            return True
        
        # Check for HTTP status codes
        if hasattr(error, 'status_code'):
            status = error.status_code
            if 500 <= status < 600 or status == 429:
                return True
        
        return False
    
    async def _transition_to_open(self, merchant_id: Optional[str] = None, db: Optional[Any] = None):
        """Open circuit and log alert."""
        self.redis.set(self.key_state, CircuitState.OPEN.value)
        
        # Exponential backoff calculation
        multiplier = self.redis.incr(self.key_timeout_multiplier)
        current_timeout = self.timeout * (2 ** (multiplier - 1))
        # Cap at 24 hours just in case
        current_timeout = min(current_timeout, 86400)
        
        self.redis.expire(self.key_state, current_timeout * 2)
        logger.error(f"Circuit breaker OPENED for {self.service_name} - service appears down. Timeout: {current_timeout}s")
        
        # Alerts
        alert_msg = f"Service {self.service_name} is DOWN. Circuit breaker is now OPEN for {current_timeout}s."
        asyncio.create_task(self._send_slack_alert(alert_msg, "error"))
        
        if merchant_id and db:
            await self._create_degradation_inbox_item(merchant_id, db, current_timeout)

    async def _create_degradation_inbox_item(self, merchant_id: str, db: Any, retry_after: int):
        """Create a notification in the merchant's inbox about service degradation."""
        try:
            from app.services.inbox import InboxService
            inbox = InboxService(db, merchant_id)
            
            await inbox.create_proposal(
                proposal_type="service_degradation",
                agent_type="safety_engine",
                proposal_data={
                    "service": self.service_name,
                    "message": f"Our integration with {self.service_name.capitalize()} is currently experiencing issues. Disabling automated tasks for this service temporarily.",
                    "retry_after_seconds": retry_after,
                    "circuit_state": "OPEN"
                },
                risk_level="critical"
            )
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to create degradation InboxItem: {e}")
    
    async def _transition_to_half_open(self):
        """Transition to half-open for testing."""
        self.redis.set(self.key_state, CircuitState.HALF_OPEN.value)
        self.redis.set(self.key_half_open_calls, 0)
        logger.info(f"Circuit breaker HALF-OPEN for {self.service_name} - testing recovery")
    
    def _should_attempt_reset(self) -> bool:
        """Check if timeout has expired."""
        last_failure = self.redis.get(self.key_last_failure)
        if not last_failure:
            return True
        
        last_failure_dt = datetime.fromisoformat(last_failure)
        
        # Check current multiplier for timeout
        m_raw = self.redis.get(self.key_timeout_multiplier)
        multiplier = int(m_raw) if m_raw else 1
        current_timeout = self.timeout * (2 ** (multiplier - 1))
        
        return datetime.utcnow() - last_failure_dt > timedelta(seconds=current_timeout)
    
    async def _can_attempt_half_open_call(self) -> bool:
        """Check if we can make another test call in half-open state."""
        calls = self.redis.get(self.key_half_open_calls)
        current_calls = int(calls) if calls else 0
        
        if current_calls >= self.half_open_max_calls:
            await self._transition_to_open()
            return False
        
        self.redis.incr(self.key_half_open_calls)
        return True
    
    def _get_retry_seconds(self) -> int:
        """Calculate seconds until retry is allowed."""
        last_failure = self.redis.get(self.key_last_failure)
        if not last_failure:
            return self.timeout
        
        last_failure_dt = datetime.fromisoformat(last_failure)
        
        # Check current multiplier for timeout
        m_raw = self.redis.get(self.key_timeout_multiplier)
        multiplier = int(m_raw) if m_raw else 1
        current_timeout = self.timeout * (2 ** (multiplier - 1))
        
        elapsed = (datetime.utcnow() - last_failure_dt).total_seconds()
        return max(1, int(current_timeout - elapsed))
    
    def get_status(self) -> dict:
        """Get current circuit breaker status for monitoring."""
        state = self._get_state()
        failures = self.redis.get(self.key_failures)
        last_failure = self.redis.get(self.key_last_failure)
        
        return {
            "service": self.service_name,
            "state": state.value,
            "failure_count": int(failures) if failures else 0,
            "failure_threshold": self.failure_threshold,
            "last_failure": last_failure,
            "timeout_seconds": self.timeout,
        }
    
    def reset(self):
        """Manually reset circuit breaker (for ops)."""
        self.redis.delete(self.key_state)
        self.redis.delete(self.key_failures)
        self.redis.delete(self.key_last_failure)
        self.redis.delete(self.key_half_open_calls)
        logger.info(f"Circuit breaker manually reset for {self.service_name}")


# =============================================================================
# Pre-configured Circuit Breakers
# =============================================================================

def get_klaviyo_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for Klaviyo API."""
    return CircuitBreaker(
        service_name="klaviyo",
        failure_threshold=5,
        timeout_seconds=60
    )


def get_twilio_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for Twilio API."""
    return CircuitBreaker(
        service_name="twilio",
        failure_threshold=5,
        timeout_seconds=60
    )


def get_shopify_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for Shopify API."""
    return CircuitBreaker(
        service_name="shopify",
        failure_threshold=10,  # More tolerance for Shopify
        timeout_seconds=30
    )


def get_all_circuit_statuses() -> dict:
    """Get status of all circuit breakers."""
    return {
        "klaviyo": get_klaviyo_circuit_breaker().get_status(),
        "twilio": get_twilio_circuit_breaker().get_status(),
        "shopify": get_shopify_circuit_breaker().get_status(),
    }
