"""
Agent models - thoughts, reasoning, and execution tracking.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, Index, Text, Numeric, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class AgentThought(Base, UUIDMixin, TimestampMixin):
    """
    Stores the internal reasoning and step-by-step logic of autonomous agents.
    Surfaces the 'why' behind agent decisions to the merchant.
    """
    __tablename__ = "agent_thoughts"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)

    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)  # observer, strategy, matchmaker, etc.
    execution_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)

    thought_type: Mapped[str] = mapped_column(String(50))  # analysis, decision, calculation, warning
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detailed_reasoning: Mapped[Optional[dict]] = mapped_column(JSON)

    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), default=Decimal("1.00"))
    step_number: Mapped[int] = mapped_column(default=1)

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="thoughts")

    __table_args__ = (
        Index("idx_thought_merchant_agent", "merchant_id", "agent_type"),
        Index("idx_thought_created", "created_at"),
    )
