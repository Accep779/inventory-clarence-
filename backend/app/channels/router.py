"""
ChannelRouter — Decides where inventory goes.

This is the decision engine that determines whether a cleared product
stays on the merchant's store only, gets listed externally, or both.

Rules are evaluated in order. First match wins.
Merchant preferences always override system defaults.
"""

from typing import List, Dict, Any
from decimal import Decimal
from app.channels.base import BaseExternalChannel
from app.channels.registry import ChannelRegistry


class ChannelRouter:

    def __init__(self, merchant: Any):
        # merchant can be a dict or Merchant model
        self.merchant = merchant
        self.available_channels = ChannelRegistry.get_enabled_channels(merchant)

    def _get_val(self, key: str, default: Any = None) -> Any:
        """Helper to get value from merchant dict or object."""
        if isinstance(self.merchant, dict):
            return self.merchant.get(key, default)
        return getattr(self.merchant, key, default)

    def route(self, product: Dict, proposal: Dict) -> Dict:
        """
        Given a product and an approved clearance proposal, decide
        which channels to use and how to allocate stock.

        Returns:
            {
                "store": True/False,                    # Always True unless explicitly disabled
                "external_channels": [                  # List of external channels to use
                    {
                        "channel": "ebay",
                        "allocated_units": 30,
                        "price": Decimal("19.99"),
                        "duration_days": 14,
                    },
                    ...
                ],
                "reasoning": "..."                      # Why this routing was chosen
            }
        """

        # Normalize inputs
        stock = product.get("stock_quantity") or product.get("total_inventory", 0)
        # Handle 'days_since_last_sale' - might rely on analysis or raw calculation
        # If not present, default to high staleness for safety or 0? 
        # Actually in proposal data we expect analyzed fields.
        staleness = product.get("days_since_last_sale", 0) 
        category = product.get("category") or product.get("product_type", "Uncategorized")
        
        proposed_price = proposal.get("proposed_price")
        if proposed_price is None:
             # Fallback if proposal structure differs
             # Attempt to calculate from discount
             curr = Decimal(str(proposal.get("current_price", 0)))
             disc = float(proposal.get("discount", 0))
             proposed_price = curr * Decimal(1 - disc)

        # --- Merchant override: external channels disabled globally ---
        if not self._get_val("external_channels_enabled", True):
            return self._store_only("Merchant has external channels disabled.")

        # --- Merchant override: category-level exclusion ---
        excluded_categories = self._get_val("external_excluded_categories", [])
        if category in excluded_categories:
            return self._store_only(f"Category '{category}' is excluded from external listing by merchant.")

        # --- Rule 1: Low stock, low staleness → store only ---
        if stock <= 20 and staleness < 14:
            return self._store_only("Stock and staleness within store-only thresholds.")

        # --- Rule 2: Moderate stock, moderate staleness → both channels ---
        if stock > 20 and 14 <= staleness <= 30:
            return self._both_channels(
                product=product,
                proposed_price=proposed_price,
                proposal=proposal,
                external_allocation_percent=40,
                reasoning="Moderate overstock with no movement. Adding external demand alongside store.",
            )

        # --- Rule 3: High stock, high staleness → both, external priority ---
        if stock > 50 and staleness > 30:
            return self._both_channels(
                product=product,
                proposed_price=proposed_price,
                proposal=proposal,
                external_allocation_percent=70,
                reasoning="Dead stock. External channels get priority allocation. Store keeps remainder.",
            )

        # --- Default: store only ---
        # If stock is high but not stale enough? Or other permutations.
        # Defaulting to store is safe.
        return self._store_only("No external routing rule matched. Defaulting to store.")

    # ---------------------------------------------------------------
    # Routing builders
    # ---------------------------------------------------------------

    def _store_only(self, reasoning: str) -> Dict:
        return {
            "store": True,
            "external_channels": [],
            "reasoning": reasoning,
        }

    def _both_channels(
        self,
        product: Dict,
        proposed_price: Decimal,
        proposal: Dict,
        external_allocation_percent: int,
        reasoning: str,
    ) -> Dict:
        stock = product.get("stock_quantity") or product.get("total_inventory", 0)
        external_units = int(stock * (external_allocation_percent / 100))
        store_units = stock - external_units

        # Distribute external units across available channels evenly
        channels = []
        if self.available_channels:
            units_per_channel = external_units // len(self.available_channels)
            remainder = external_units % len(self.available_channels)

            duration = 7 # Default days
            if "duration_hours" in proposal:
                duration = int(proposal["duration_hours"]) // 24
            elif "duration_days" in proposal:
                duration = int(proposal["duration_days"])
                
            if duration < 1: duration = 1

            for i, channel in enumerate(self.available_channels):
                allocation = units_per_channel + (1 if i < remainder else 0)
                if allocation > 0:
                    channels.append({
                        "channel": channel.channel_name,
                        "allocated_units": allocation,
                        "price": proposed_price,
                        "duration_days": duration,
                    })

        return {
            "store": True,
            "store_units": store_units,
            "external_channels": channels,
            "reasoning": reasoning,
        }
