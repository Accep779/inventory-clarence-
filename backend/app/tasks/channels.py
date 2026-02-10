"""
Celery task: Clean up external listings when a campaign ends.

When a campaign expires, any unsold inventory on external channels
must be cancelled. Stock reverts to the merchant's store.
"""

from celery import shared_task
from typing import List, Dict
import logging

from app.channels.registry import ChannelRegistry

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def cleanup_external_listings(
    self,
    campaign_id: str,
    merchant_id: str,
    listings: List[Dict],
):
    """
    Cancel all external listings for a completed campaign.

    Args:
        listings: List of dicts with {channel, listing_id} for each
                  external listing that was created during execution.
    """
    from app.database import sync_session_maker
    from app.models import Merchant
    import asyncio

    with sync_session_maker() as session:
        merchant = session.get(Merchant, merchant_id)
        if not merchant:
            logger.error("Merchant %s not found for cleanup.", merchant_id)
            return

        async def _cancel_all():
            for listing in listings:
                channel = ChannelRegistry.get_channel(listing["channel"])
                channel_context = (merchant.external_channel_credentials or {}).get(
                    listing["channel"], {}
                )
                try:
                    success = await channel.cancel_listing(
                        channel_context=channel_context,
                        external_listing_id=listing["listing_id"],
                    )
                    if success:
                        logger.info("Cancelled listing %s on %s.", listing["listing_id"], listing["channel"])
                    else:
                        logger.error("Failed to cancel listing %s on %s.", listing["listing_id"], listing["channel"])
                except Exception as e:
                    logger.error(f"Exception cancelling listing {listing['listing_id']} on {listing['channel']}: {e}")

        # Celery tasks are sync, but our adapters are async. Run in event loop.
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        loop.run_until_complete(_cancel_all())
