"""
Campaign models - execution tracking and performance metrics.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, DateTime, Numeric, ForeignKey, Index, Integer, JSON, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Campaign(Base, UUIDMixin, TimestampMixin):
    """Tracks executed clearance campaigns and their performance."""
    __tablename__ = "campaigns"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # progressive_discount, flash_sale, bundle, etc.
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, active, paused, completed

    # Targeting (stored as arrays)
    target_segments: Mapped[Optional[list]] = mapped_column(JSON)
    product_ids: Mapped[Optional[list]] = mapped_column(JSON)

    # Personalization & Learning
    content_snapshot: Mapped[Optional[dict]] = mapped_column(JSON)  # Stores the actual copy sent

    # Performance Tracking
    emails_sent: Mapped[int] = mapped_column(Integer, default=0)
    emails_opened: Mapped[int] = mapped_column(Integer, default=0)
    emails_clicked: Mapped[int] = mapped_column(Integer, default=0)
    sms_sent: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    origin_execution_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="campaigns")

    __table_args__ = (
        Index("idx_campaign_merchant_status", "merchant_id", "status"),
    )


class LLMUsageLog(Base, UUIDMixin, TimestampMixin):
    """
    Tracks token usage and costs for all LLM calls.
    """
    __tablename__ = 'llm_usage_logs'

    merchant_id: Mapped[Optional[str]] = mapped_column(ForeignKey('merchants.id'))
    provider: Mapped[str] = mapped_column(String(50))  # anthropic, openai, google
    model: Mapped[str] = mapped_column(String(100))
    task_type: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    latency: Mapped[Optional[float]] = mapped_column(Numeric(10, 3))
    used_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)


class Ledger(Base, UUIDMixin, TimestampMixin):
    """
    Stores de-duplicated revenue attributed to agent actions.
    """
    __tablename__ = "ledger_entries"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)
    order_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    agent_stake: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    attribution_source: Mapped[str] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=True)
