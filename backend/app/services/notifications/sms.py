
import logging
import os
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

class TwilioService:
    """
    Service for sending system-level SMS notifications (e.g. CIBA magic links).
    Uses platform credentials, not merchant credentials.
    """
    
    def __init__(self):
        # Platform credentials from env
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_FROM_NUMBER")
        
        if self.account_sid and self.auth_token:
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            logger.warning("Twilio credentials not found. SMS notifications disabled.")

    async def send_sms(self, to_number: str, body: str) -> bool:
        """Send an SMS message."""
        if not self.client or not self.from_number:
            logger.warning("Attempted to send SMS but Twilio is not configured.")
            return False
            
        try:
            message = self.client.messages.create(
                body=body,
                from_=self.from_number,
                to=to_number
            )
            logger.info(f"SMS sent to {to_number}: {message.sid}")
            return True
        except TwilioRestException as e:
            logger.error(f"Failed to send SMS to {to_number}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending SMS: {e}")
            return False
