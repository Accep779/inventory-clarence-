"""
Governor models - risk policies and autonomous control.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, ForeignKey, Index, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


class RiskPolicy(Base, UUIDMixin, TimestampMixin):
    """
    Defines the Risk Matrix rules for different agents and action types.
    """
    __tablename__ = "governor_risk_policies"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)

    agent_type: Mapped[str] = mapped_column(String(50), index=True)
    action_type: Mapped[str] = mapped_column(String(50))
    risk_level: Mapped[str] = mapped_column(String(20))  # low, moderate, high, critical

    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    min_confidence: Mapped[float] = mapped_column(default=0.95)
    min_trust_score: Mapped[float] = mapped_column(default=0.90)

    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
