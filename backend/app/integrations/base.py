from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

class BaseConnector(ABC):
    """
    Abstract Base Class for all External Integrations.
    """
    
    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.config = kwargs

    @abstractmethod
    async def create_campaign(self, name: str, subject: str, body_html: str, target_segment_ids: List[str], idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates a marketing campaign (draft) in the external platform.
        """
        pass

    @abstractmethod
    async def send_transactional(self, to_email: str, subject: str, body: str, idempotency_key: Optional[str] = None) -> bool:
        """
        Sends a single transactional message immediately.
        """
        pass

