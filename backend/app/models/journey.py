"""
Journey models - customer reactivation and touch tracking.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, DateTime, Numeric, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class CommercialJourney(Base, UUIDMixin, TimestampMixin):
    """
    Tracks the state of a multi-step customer re-engagement sequence.
    """
    __tablename__ = "commercial_journeys"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)

    # State
    journey_type: Mapped[str] = mapped_column(String(50), default="reactivation")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, paused, completed, converted, failed
    current_touch: Mapped[int] = mapped_column(Integer, default=1)

    # Scheduling
    next_touch_due_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_touch_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer")
    logs: Mapped[List["TouchLog"]] = relationship("TouchLog", back_populates="journey", cascade="all, delete-orphan")


class MerchantJourney(Base, UUIDMixin, TimestampMixin):
    """
    Tracks long-term merchant goals (e.g., "Liquidate $50k").
    Agents work on "Episodes" that contribute to this Journey.
    """
    __tablename__ = "merchant_journeys"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)

    title: Mapped[str] = mapped_column(String(255))
    journey_type: Mapped[str] = mapped_column(String(50))  # e.g., "liquidation_sprint"

    # SMART Goal fields
    target_metric: Mapped[str] = mapped_column(String(50))  # e.g., "revenue"
    target_value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    current_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    deadline_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, completed, failed


class TouchLog(Base, UUIDMixin, TimestampMixin):
    """
    Audit trail for every communication dispatched in a journey.
    """
    __tablename__ = "touch_logs"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True)
    journey_id: Mapped[Optional[str]] = mapped_column(ForeignKey("commercial_journeys.id", ondelete="CASCADE"))
    campaign_id: Mapped[Optional[str]] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    external_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)  # external SID or Klaviyo ID
    customer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))

    touch_stage: Mapped[int] = mapped_column(Integer, default=1)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # email, sms
    sent_content: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="sent")  # sent, delivered, failed, opened, clicked

    # Relationships
    journey: Mapped["CommercialJourney"] = relationship("CommercialJourney", back_populates="logs")
