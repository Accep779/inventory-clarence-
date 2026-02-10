import httpx
import logging
from typing import List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, before_sleep_log
from app.integrations.base import BaseConnector
from app.integrations.circuit_breaker import get_twilio_circuit_breaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)

def is_retryable_httpx_error(exception):
    """Return True if exception is a retryable HTTP error (429, 5xx) from httpx."""
    
    # Duck typing to handle potential import mismatches or mock objects
    if hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
        status = exception.response.status_code
        return status == 429 or status >= 500
        
    # Check for timeout by name or attribute
    exc_name = type(exception).__name__
    if 'Timeout' in exc_name or 'ConnectError' in exc_name:
         return True
         
    # Fallback to isinstance if possible (standard path)
    if isinstance(exception, (httpx.ConnectError, httpx.TimeoutException)):
        return True
        
    return False

class TwilioConnector(BaseConnector):
    """
    Twilio Adapter for SMS (Async).
    """
    def __init__(self, api_key: str, from_number: Optional[str] = None):
        super().__init__(api_key)
        self.from_number = from_number or "+15555555555"

    def _parse_creds(self):
        try:
            sid, token = self.api_key.split(":")
            return sid, token
        except ValueError:
            logger.error("Invalid Twilio Creds. Format must be AccountSID:AuthToken")
            return None, None

    async def create_campaign(self, name: str, subject: str, body_html: str, target_segment_ids: List[str], idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        logger.warning("Twilio does not support 'Campaigns' natively.")
        return {"error": "Not Supported"}

    @retry(
        retry=retry_if_exception(is_retryable_httpx_error),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def send_transactional(self, to_email: str, subject: str, body: str, idempotency_key: Optional[str] = None) -> bool:

        """
        Actually sends SMS.
        """
        sid, token = self._parse_creds()
        if not sid:
            return False
            
        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        
        payload = {
            "To": to_email,
            "From": self.from_number,
            "Body": body
        }
        
        headers = {}
        if idempotency_key:
            headers["X-Twilio-Idempotency-Token"] = idempotency_key

        async def _execute():
            try:
                async with httpx.AsyncClient(auth=(sid, token), timeout=10.0) as client:
                    response = await client.post(url, data=payload, headers=headers)

                    response.raise_for_status()
                    res_data = response.json()
                    sid_val = res_data.get('sid')
                    logger.info(f"Twilio SMS sent to {to_email}. SID: {sid_val}")
                    return {"id": sid_val, "status": "sent"}
            except Exception as e:
                if is_retryable_httpx_error(e):
                     raise e # Let tenacity handle it
                logger.error(f"Twilio Error: {str(e)}")
                return False

        try:
            breaker = get_twilio_circuit_breaker()
            return await breaker.call(
                _execute,
                merchant_id=self.config.get("merchant_id"),
                db=self.config.get("db")
            )
        except CircuitBreakerOpenError:
            return False
        except Exception as e:
            # Final failure if tenacity gives up or non-retryable error
            return False
