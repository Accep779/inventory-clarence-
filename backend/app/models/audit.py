"""
Audit models - comprehensive logging for compliance and transparency.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, Index, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin


class AuditLog(Base, UUIDMixin, TimestampMixin):
    """
    Audit trail for human and agent actions in the system.
    Ensures compliance and transparency in HITL operations.
    """
    __tablename__ = "audit_logs"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(255))  # For human actions

    action: Mapped[str] = mapped_column(String(100), nullable=False)  # View, Edit, Approve, Reject, GenerateUGC
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # InboxItem, Campaign, Settings
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)

    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)

    # Actor Context (Auth0 Pattern)
    actor_type: Mapped[str] = mapped_column(String(20), default="system")  # human, agent, system
    actor_agent_type: Mapped[Optional[str]] = mapped_column(String(50))  # observer, strategy, etc.
    delegated_by: Mapped[Optional[str]] = mapped_column(String(36))  # Merchant ID if delegated
    client_id: Mapped[Optional[str]] = mapped_column(String(100))  # Agent Client ID
    execution_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)

    # Authorization Context
    authorization_id: Mapped[Optional[str]] = mapped_column(String(100))  # CIBA request ID
    scopes_used: Mapped[Optional[list]] = mapped_column(JSON)  # Scopes that allowed this action

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant")

    __table_args__ = (
        # Primary query patterns
        Index("idx_audit_merchant_created", "merchant_id", "created_at"),  # List audit logs for merchant
        Index("idx_audit_entity", "entity_type", "entity_id"),  # Find all actions on specific entity
        Index("idx_audit_action_type", "action", "entity_type"),  # Filter by action type
        Index("idx_audit_execution", "execution_id"),  # Forensic tracing
        Index("idx_audit_actor", "actor_type", "actor_agent_type"),  # Find actions by specific actors
        Index("idx_audit_created", "created_at"),  # Time-based cleanup/archival
    )


class ActionReversal(Base, UUIDMixin, TimestampMixin):
    """
    Tracks how to 'undo' a specific agent or human operation.
    Ensures that high-risk forensic changes are reversible.
    """
    __tablename__ = "action_reversals"

    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False)
    audit_log_id: Mapped[str] = mapped_column(ForeignKey("audit_logs.id"), nullable=False)

    # State Capture
    reversal_type: Mapped[str] = mapped_column(String(50))  # delete_discount, remove_tag, revert_price
    original_state: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="available")  # available, executed, failed
    reversal_error: Mapped[Optional[str]] = mapped_column(Text)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    merchant: Mapped["Merchant"] = relationship("Merchant")
    audit_log: Mapped["AuditLog"] = relationship("AuditLog")

    __table_args__ = (
        Index("idx_reversal_merchant", "merchant_id"),
    )
