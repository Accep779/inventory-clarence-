import requests
import logging
from typing import List, Dict, Any, Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, before_sleep_log

from app.integrations.base import BaseConnector
from app.integrations.circuit_breaker import get_klaviyo_circuit_breaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)

def is_retryable_error(exception):
    """Return True if exception is a retryable HTTP error (429, 5xx)."""
    if isinstance(exception, requests.exceptions.HTTPError):
        status = exception.response.status_code
        return status == 429 or status >= 500
    return False

class KlaviyoConnector(BaseConnector):
    """
    Klaviyo Adapter using raw HTTP requests.
    """
    BASE_URL = "https://a.klaviyo.com/api"

    def _headers(self, idempotency_key: Optional[str] = None):
        headers = {
            "Authorization": f"Klaviyo-API-Key {self.api_key}",
            "accept": "application/vnd.api+json",
            "content-type": "application/vnd.api+json",
            "revision": "2023-02-22"
        }
        if idempotency_key:
            headers["idempotency-key"] = idempotency_key
        return headers

    @retry(
        retry=retry_if_exception(is_retryable_error),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def create_campaign(self, name: str, subject: str, body_html: str, target_segment_ids: List[str], idempotency_key: Optional[str] = None) -> Dict[str, Any]:

        """
        Creates a Campaign in Klaviyo.
        """
        url = f"{self.BASE_URL}/campaigns"
        
        payload = {
            "data": {
                "type": "campaign",
                "attributes": {
                    "name": name,
                    "audiences": {
                        "included": target_segment_ids
                    },
                    "send_strategy": {
                        "method": "static"
                    },
                    "campaign_messages": {
                        "data": [
                            {
                                "type": "campaign-message",
                                "attributes": {
                                    "channel": "email",
                                    "label": name,
                                    "content": {
                                        "subject": subject,
                                        "html_body": body_html,
                                        "from_email": self.config.get("from_email", "notifications@cephly-store.com"),
                                        "from_label": self.config.get("from_label", "Store Assistant")
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
        
        async def _execute():
            # Note: Cephly used requests.post synchronously. I'll stick to it or wrap in executor.
            # Given it's a connector, async is better. I'll use httpx if available or just wrap.
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: requests.post(url, json=payload, headers=self._headers(idempotency_key), timeout=30))

            response.raise_for_status()
            data = response.json()
            external_id = data['data']['id']
            logger.info(f"Klaviyo Campaign Created: {external_id}")
            return {"id": external_id, "status": "created"}
            
        try:
            breaker = get_klaviyo_circuit_breaker()
            return await breaker.call(
                _execute, 
                merchant_id=self.config.get("merchant_id"),
                db=self.config.get("db")
            )
        except CircuitBreakerOpenError:
            raise
        except Exception as e:
            # Logger is handled by tenacity for retries, but we catch final failures here if needed
            # However, we re-raise so the caller knows it failed
            if not is_retryable_error(e):
                 logger.error(f"Klaviyo API Error (Non-Retryable): {str(e)}")
            raise e

    @retry(
        retry=retry_if_exception(is_retryable_error),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def send_transactional(self, to_email: str, subject: str, body: str, idempotency_key: Optional[str] = None) -> bool:

        """
        Sends a 1:1 message by triggering a Klaviyo event.
        
        Requires a Flow in Klaviyo to be set up to listen for the 'Transaction Trigger' event.
        """
        url = f"{self.BASE_URL}/events"
        
        payload = {
            "data": {
                "type": "event",
                "attributes": {
                    "properties": {
                        "subject": subject,
                        "message_body": body
                    },
                    "metric": {
                        "data": {
                            "type": "metric",
                            "attributes": {
                                "name": "Direct Agent Message"
                            }
                        }
                    },
                    "profile": {
                        "data": {
                            "type": "profile",
                            "attributes": {
                                "email": to_email
                            }
                        }
                    }
                }
            }
        }
        
        async def _execute():
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: requests.post(url, json=payload, headers=self._headers(idempotency_key), timeout=30))

            # Klaviyo returns 202 Accepted for events
            if response.status_code in [201, 202]:
                logger.info(f"Klaviyo Transactional Event Triggered for {to_email}")
                return True
            else:
                # Raise for status specifically to trigger retries if it's a 429/5xx
                # If it's 400, raise_for_status will raise, but is_retryable will be false
                response.raise_for_status() 
                logger.error(f"Klaviyo Transactional Failed: {response.text}")
                return False

        try:
            breaker = get_klaviyo_circuit_breaker()
            return await breaker.call(
                _execute,
                merchant_id=self.config.get("merchant_id"),
                db=self.config.get("db")
            )
        except CircuitBreakerOpenError:
            return False
        except Exception as e:
            if is_retryable_error(e):
                raise e # Let tenacity handle it
            logger.error(f"Klaviyo Transactional Error: {str(e)}")
            return False
