"""
BaseExternalChannel — Contract for all external listing platforms.

A Platform Adapter (adapters/base.py) manages the merchant's own store:
    authenticate, sync, update_price, webhooks.

An External Channel (this file) manages LISTING inventory on third-party
platforms to reach new buyers:
    create_listing, monitor_listing, cancel_listing, sync_sales.

These are fundamentally different operations. A merchant's store is where
they sell permanently. An external channel is where Cephly places inventory
temporarily to clear it.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ExternalListing:
    """Represents a live listing on an external platform."""
    channel_name: str                   # "ebay", "amazon"
    external_listing_id: str            # The ID assigned by the external platform
    platform_product_id: str            # Original product ID from merchant's store
    platform_variant_id: str            # Original variant ID
    title: str
    listed_price: Decimal
    stock_allocated: int                # How many units were sent to this channel
    status: str                         # "active", "sold", "expired", "cancelled"
    created_at: datetime
    sold_at: Optional[datetime] = None
    units_sold: int = 0


@dataclass
class ListingResult:
    """Confirmation of a listing creation attempt."""
    success: bool
    external_listing_id: Optional[str]
    channel_name: str
    error_message: Optional[str] = None


@dataclass
class SyncedSale:
    """A sale that occurred on an external channel. Reported back to Cephly."""
    external_listing_id: str
    channel_name: str
    units_sold: int
    revenue: Decimal
    sold_at: datetime
    buyer_email: Optional[str]          # If the platform exposes this


class BaseExternalChannel(ABC):
    """
    Abstract base for all external listing channels.

    Every external platform (eBay, Amazon, etc.) implements this.
    The ChannelRouter calls these methods. The core system never
    imports a channel-specific module directly.
    """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Unique identifier: 'ebay', 'amazon', 'wholesale', etc."""
        pass

    @abstractmethod
    async def authenticate(self, credentials: Dict) -> Dict:
        """
        Authenticate with the external platform.
        Each platform has its own credential model (API keys, OAuth, etc.).
        Returns a context dict stored on the Merchant record under
        `external_channel_credentials[channel_name]`.
        """
        pass

    @abstractmethod
    async def create_listing(
        self,
        channel_context: Dict,
        product: Dict,
        price: Decimal,
        quantity: int,
        duration_days: int,
    ) -> ListingResult:
        """
        Create a listing on the external platform.

        Args:
            channel_context: Auth credentials for this channel
            product:         Normalized product data (title, description, images, category)
            price:           The clearance price to list at
            quantity:        How many units to allocate to this channel
            duration_days:   How long the listing should stay active

        The listing must go live immediately. When this returns success,
        the product must be purchasable on the external platform.
        """
        pass

    @abstractmethod
    async def monitor_listing(
        self,
        channel_context: Dict,
        external_listing_id: str,
    ) -> ExternalListing:
        """
        Check the current state of a listing.
        Called by the ObserverAgent on a schedule to track sales velocity
        on external channels.
        """
        pass

    @abstractmethod
    async def cancel_listing(
        self,
        channel_context: Dict,
        external_listing_id: str,
    ) -> bool:
        """
        Cancel an active listing. Used when:
        - All stock allocated to this channel has sold
        - The campaign ends and unsold stock reverts to the store
        - The merchant manually cancels
        """
        pass

    @abstractmethod
    async def sync_sales(
        self,
        channel_context: Dict,
        since: datetime,
    ) -> List[SyncedSale]:
        """
        Pull all sales that occurred on this channel since a given timestamp.
        Called by the nightly aggregator to update campaign performance data
        and feed the GlobalStrategyTemplate.
        """
        pass
