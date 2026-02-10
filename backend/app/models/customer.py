"""
Customer models - RFM segmentation and purchase behavior tracking.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, DateTime, Numeric, ForeignKey, Index, Integer, BigInteger, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Customer(Base, UUIDMixin, TimestampMixin):
    """
    Represents a Shopify customer with RFM segmentation.
    The Matchmaker Agent updates RFM scores daily.
    """
    __tablename__ = "customers"

    shopify_customer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)

    # Contact Info
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))

    # RFM Scoring (Updated by Matchmaker Agent)
    recency_score: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5
    frequency_score: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5
    monetary_score: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5
    rfm_segment: Mapped[Optional[str]] = mapped_column(String(50))  # champions, loyal, at_risk, lapsed, lost, new, potential

    # Purchase Behavior
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    total_spent: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    last_order_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    avg_order_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # Engagement Preferences
    email_optin: Mapped[bool] = mapped_column(Boolean, default=False)
    sms_optin: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="customers")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="customer")

    __table_args__ = (
        Index("idx_customer_merchant_segment", "merchant_id", "rfm_segment"),
        Index("idx_customer_last_order", "last_order_date"),
    )
