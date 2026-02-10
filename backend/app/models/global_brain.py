"""
Global Brain models - cross-tenant learning and pattern recognition.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, Index, Numeric, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin, TimestampMixin


class GlobalStrategyPattern(Base, UUIDMixin, TimestampMixin):
    """
    Stores anonymized, high-performance strategy patterns learned across all stores.
    """
    __tablename__ = "global_strategy_patterns"

    pattern_key: Mapped[str] = mapped_column(String(255), index=True)
    industry_type: Mapped[str] = mapped_column(String(50), nullable=True)
    strategy_key: Mapped[str] = mapped_column(String(50), nullable=False)

    # Combined benchmarks
    p50_conversion: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    p90_conversion: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0)
    avg_roi_p50: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    recommendation_score: Mapped[float] = mapped_column(Float, default=0)
    sample_count: Mapped[int] = mapped_column(default=0)  # Minimum N>=100 for validity
    context_criteria: Mapped[dict] = mapped_column(JSON)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
