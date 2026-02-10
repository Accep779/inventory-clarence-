"""
Product models - inventory tracking with velocity and dead stock detection.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, Text, Boolean, Integer, BigInteger, DateTime, Numeric, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, VersionMixin


class Product(Base, UUIDMixin, TimestampMixin, VersionMixin):
    """
    Represents a Shopify product with velocity and dead stock tracking.
    The Observer Agent updates these fields daily.
    """
    __tablename__ = "products"

    shopify_product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)

    # Basic Info
    title: Mapped[str] = mapped_column(Text, nullable=False)
    handle: Mapped[str] = mapped_column(String(255), nullable=False)
    product_type: Mapped[Optional[str]] = mapped_column(String(255))
    vendor: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="active")  # active, archived, draft

    # Inventory
    total_inventory: Mapped[int] = mapped_column(Integer, default=0)
    variant_count: Mapped[int] = mapped_column(Integer, default=0)

    # Sales Velocity (Updated by Observer Agent Daily)
    units_sold_30d: Mapped[int] = mapped_column(Integer, default=0)
    units_refunded_30d: Mapped[int] = mapped_column(Integer, default=0)
    units_sold_60d: Mapped[int] = mapped_column(Integer, default=0)
    units_sold_90d: Mapped[int] = mapped_column(Integer, default=0)
    revenue_30d: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    last_sale_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Dead Stock Classification (Set by Observer Agent)
    velocity_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    is_dead_stock: Mapped[bool] = mapped_column(Boolean, default=False)
    dead_stock_severity: Mapped[Optional[str]] = mapped_column(String(20))  # critical, high, moderate, low
    days_since_last_sale: Mapped[Optional[int]] = mapped_column(Integer)

    # Cost Tracking
    cost_per_unit: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    holding_cost_per_day: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # Soft Delete (preserves order history references)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="products")
    variants: Mapped[List["ProductVariant"]] = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    order_items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="product")

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def inventory_value(self) -> float:
        """Calculated inventory value based on cost."""
        cost = float(self.cost_per_unit or 0)
        return cost * self.total_inventory

    __table_args__ = (
        Index("idx_product_merchant_dead", "merchant_id", "is_dead_stock"),
        Index("idx_product_velocity", "velocity_score"),
        Index("idx_product_last_sale", "last_sale_date"),
    )


class ProductVariant(Base, UUIDMixin, TimestampMixin):
    """Represents a Shopify product variant (size, color, etc.)."""
    __tablename__ = "product_variants"

    shopify_variant_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[Optional[str]] = mapped_column(String(255))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    compare_at_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    inventory_quantity: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped["Product"] = relationship("Product", back_populates="variants")

    __table_args__ = (
        Index("idx_variant_product", "product_id"),
    )


class FloorPricing(Base, UUIDMixin, TimestampMixin):
    """
    Per-product pricing constraints for clearance strategies.
    Prevents agents from suggesting discounts that violate margin requirements.
    """
    __tablename__ = "floor_pricing"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)

    # Product linkage (at least one should be set for matching)
    sku: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    shopify_product_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)
    product_id: Mapped[Optional[str]] = mapped_column(ForeignKey("products.id"))

    # Pricing constraints
    cost_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    min_margin_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    floor_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    liquidation_mode: Mapped[bool] = mapped_column(Boolean, default=False)

    # Notes and metadata
    notes: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), default="csv_upload")  # csv_upload, manual, api

    __table_args__ = (
        Index("idx_floor_pricing_merchant", "merchant_id"),
        Index("idx_floor_pricing_sku", "sku"),
    )
