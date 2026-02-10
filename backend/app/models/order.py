"""
Order models - transaction history and line items.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, DateTime, Numeric, ForeignKey, Index, Integer, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class Order(Base, UUIDMixin, TimestampMixin):
    """Represents a Shopify order for analytics."""
    __tablename__ = "orders"

    shopify_order_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)
    customer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("customers.id"))

    order_number: Mapped[str] = mapped_column(String(50), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    total_tax: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="orders")
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="orders")
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_order_merchant_date", "merchant_id", "created_at"),
        Index("idx_order_customer", "customer_id"),
    )


class OrderItem(Base, UUIDMixin, TimestampMixin):
    """Represents a line item in an order."""
    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[Optional[str]] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped[Optional["Product"]] = relationship("Product", back_populates="order_items")

    __table_args__ = (
        Index("idx_orderitem_order", "order_id"),
        Index("idx_orderitem_product", "product_id"),
    )
