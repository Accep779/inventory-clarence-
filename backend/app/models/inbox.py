"""
Inbox models - agent proposals and merchant approvals.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, DateTime, Numeric, ForeignKey, Index, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, VersionMixin


class InboxItem(Base, UUIDMixin, TimestampMixin, VersionMixin):
    """
    Represents a proposal from an Agent to the Merchant.
    The Inbox-First Control Surface displays these for approval.
    """
    __tablename__ = "inbox_items"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)

    # Proposal Type
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # dead_stock_alert, clearance_proposal, liquidation_offer
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, approved, rejected, executed, GENERATING, FAILED

    # Proposal Data (JSON blob with strategy details)
    proposal_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Autonomy & Risk
    risk_level: Mapped[str] = mapped_column(String(20), default="low")  # low, moderate, critical

    # Agent Metadata
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)  # observer, strategy, matchmaker, broker
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    origin_execution_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)

    # Conversational Interface
    chat_history: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # Merchant Interaction
    viewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="inbox_items")

    # Valid status transitions (state machine)
    VALID_TRANSITIONS = {
        'pending': ['approved', 'rejected', 'executing'],
        'approved': ['executing', 'expired'],
        'executing': ['executed', 'failed'],
        'failed': ['pending'],  # Allow retry
        'rejected': [],
        'executed': [],
        'expired': [],
    }

    def can_transition_to(self, new_status: str) -> bool:
        """Check if transition to new status is valid."""
        return new_status in self.VALID_TRANSITIONS.get(self.status, [])

    def transition_to(self, new_status: str) -> None:
        """Transition to new status if valid, otherwise raise error."""
        if not self.can_transition_to(new_status):
            raise ValueError(f"Invalid transition: {self.status} -> {new_status}")
        self.status = new_status

    __table_args__ = (
        Index("idx_inbox_merchant_status", "merchant_id", "status"),
        Index("idx_inbox_created", "created_at"),
    )


class PendingNotification(Base, UUIDMixin, TimestampMixin):
    """
    Stores deferred low-priority notifications for batch delivery.
    """
    __tablename__ = "pending_notifications"

    merchant_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)

    priority: Mapped[str] = mapped_column(String(20), default="low")  # low, high
    channel: Mapped[str] = mapped_column(String(50), default="email")
    content: Mapped[str] = mapped_column(Text)

    # Metadata for grouping
    topic: Mapped[Optional[str]] = mapped_column(String(100))
