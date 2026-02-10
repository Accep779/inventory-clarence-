"""
Store DNA models - merchant identity and brand understanding.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, DateTime, Numeric, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class StoreDNA(Base, UUIDMixin, TimestampMixin):
    """
    Stores the merchant's unique identity metrics and creative patterns.
    Enhanced with brand guide uploads, URL scraping, and identity description.
    """
    __tablename__ = "store_dna"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)

    # Financial DNA
    aov_p50: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    aov_p90: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    total_revenue_30d: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))

    # Creative DNA
    brand_tone: Mapped[str] = mapped_column(String(50), default="Modern")
    industry_type: Mapped[str] = mapped_column(String(50), default="Retail")
    brand_values: Mapped[list] = mapped_column(JSON, default=list)

    # Merchant-uploaded brand guide
    brand_guide_raw: Mapped[Optional[str]] = mapped_column(Text)  # Raw markdown content
    brand_guide_parsed: Mapped[Optional[dict]] = mapped_column(JSON)  # LLM-extracted structured data

    # URL Scraping results
    scraped_homepage_meta: Mapped[Optional[dict]] = mapped_column(JSON)  # title, description, OG tags
    scraped_about_content: Mapped[Optional[str]] = mapped_column(Text)  # About page text
    scraped_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Merchant identity description (freeform text)
    identity_description: Mapped[Optional[str]] = mapped_column(Text)

    # Industry-Specific RFM Calibration
    rfm_recency_thresholds: Mapped[Optional[list]] = mapped_column(JSON)  # [30, 60, 90, 180] days
    rfm_frequency_thresholds: Mapped[Optional[list]] = mapped_column(JSON)  # [1, 2, 5, 10] orders
    rfm_monetary_thresholds: Mapped[Optional[list]] = mapped_column(JSON)  # [$50, $100, $250, $500]

    # Metadata
    last_analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    raw_discovery_snapshot: Mapped[Optional[dict]] = mapped_column(JSON)

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="dna")


class StrategyTemplate(Base, UUIDMixin, TimestampMixin):
    """
    High-confidence actionable templates derived from global patterns.
    """
    __tablename__ = "global_strategy_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    industry_type: Mapped[str] = mapped_column(String(50))
    skill_name: Mapped[str] = mapped_column(String(50))

    recommended_discount: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    expected_lift: Mapped[Decimal] = mapped_column(Numeric(5, 2))
