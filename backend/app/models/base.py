"""
SQLAlchemy Base and mixins for all models.

This module provides:
- Base declarative class for all models
- Common mixins for timestamps, UUIDs, and soft deletes
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class UUIDMixin:
    """Mixin that adds a UUID primary key."""

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


class SoftDeleteMixin:
    """Mixin that adds soft delete capability."""

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    @property
    def is_deleted(self) -> bool:
        """Check if record has been soft deleted."""
        return self.deleted_at is not None


class VersionMixin:
    """Mixin that adds optimistic locking with version number."""

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False
    )
