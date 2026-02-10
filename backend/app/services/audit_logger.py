"""
Audit Logging Service
=====================

Provides comprehensive audit logging for compliance and transparency.

Usage:
    from app.services.audit_logger import AuditLogger, AuditAction

    # Simple logging
    await AuditLogger.log(
        merchant_id="uuid",
        action=AuditAction.APPROVE,
        entity_type="InboxItem",
        entity_id="uuid",
        actor_type="human",
        user_id="user@example.com"
    )

    # With before/after state
    await AuditLogger.log_with_state(
        merchant_id="uuid",
        action=AuditAction.UPDATE,
        entity_type="Campaign",
        entity_id="uuid",
        before={"status": "draft"},
        after={"status": "active"},
        actor_type="agent",
        actor_agent_type="execution"
    )
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Optional, Any
from contextvars import ContextVar

from sqlalchemy import select
from app.database import async_session_maker
from app.models import AuditLog, ActionReversal

logger = logging.getLogger(__name__)

# Context vars for automatic context propagation
_current_user_id: ContextVar[Optional[str]] = ContextVar("audit_user_id", default=None)
_current_execution_id: ContextVar[Optional[str]] = ContextVar("audit_execution_id", default=None)
_current_auth_id: ContextVar[Optional[str]] = ContextVar("audit_auth_id", default=None)


class AuditAction(str, Enum):
    """Standardized audit actions."""
    # Read operations
    VIEW = "view"
    LIST = "list"
    EXPORT = "export"

    # Write operations
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

    # Approval operations
    APPROVE = "approve"
    REJECT = "reject"
    EXECUTE = "execute"

    # Auth operations
    LOGIN = "login"
    LOGOUT = "logout"
    REFRESH_TOKEN = "refresh_token"
    REVOKE_TOKEN = "revoke_token"

    # System operations
    SYNC = "sync"
    SCAN = "scan"
    GENERATE = "generate"


class AuditEntityType(str, Enum):
    """Standardized entity types."""
    INBOX_ITEM = "InboxItem"
    CAMPAIGN = "Campaign"
    MERCHANT = "Merchant"
    PRODUCT = "Product"
    CUSTOMER = "Customer"
    ORDER = "Order"
    SETTINGS = "Settings"
    INTEGRATION = "Integration"


class AuditLogger:
    """
    Centralized audit logging service.

    Provides methods for logging all significant actions in the system.
    """

    @staticmethod
    async def log(
        merchant_id: str,
        action: AuditAction | str,
        entity_type: AuditEntityType | str,
        entity_id: str,
        actor_type: str = "system",
        actor_agent_type: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        delegated_by: Optional[str] = None,
        client_id: Optional[str] = None,
        scopes_used: Optional[list] = None,
    ) -> AuditLog:
        """
        Create an audit log entry.

        Args:
            merchant_id: The merchant the action was performed for
            action: The action that was performed
            entity_type: The type of entity affected
            entity_id: The ID of the entity affected
            actor_type: "human", "agent", or "system"
            actor_agent_type: For agents: "observer", "strategy", "execution", etc.
            user_id: For human actors: the user ID
            metadata: Additional JSON-serializable context
            delegated_by: If action was delegated, the delegator's merchant ID
            client_id: OAuth client ID for the actor
            scopes_used: OAuth scopes that authorized this action

        Returns:
            The created AuditLog entry
        """
        async with async_session_maker() as session:
            audit_entry = AuditLog(
                merchant_id=merchant_id,
                action=action.value if isinstance(action, Enum) else action,
                entity_type=entity_type.value if isinstance(entity_type, Enum) else entity_type,
                entity_id=entity_id,
                actor_type=actor_type,
                actor_agent_type=actor_agent_type,
                user_id=user_id or _current_user_id.get(),
                execution_id=_current_execution_id.get(),
                authorization_id=_current_auth_id.get(),
                delegated_by=delegated_by,
                client_id=client_id,
                scopes_used=scopes_used,
                metadata_json=metadata,
            )

            session.add(audit_entry)
            await session.commit()
            await session.refresh(audit_entry)

            logger.debug(
                f"Audit logged: {action} on {entity_type}:{entity_id} "
                f"by {actor_type} for merchant {merchant_id}"
            )

            return audit_entry

    @staticmethod
    async def log_with_state(
        merchant_id: str,
        action: AuditAction | str,
        entity_type: AuditEntityType | str,
        entity_id: str,
        before: Optional[dict] = None,
        after: Optional[dict] = None,
        **kwargs
    ) -> AuditLog:
        """
        Log an action with before/after state for change tracking.

        Args:
            before: State before the action
            after: State after the action
            **kwargs: Additional arguments passed to log()

        Returns:
            The created AuditLog entry
        """
        metadata = kwargs.pop("metadata", {}) or {}
        metadata["state_change"] = {
            "before": before,
            "after": after,
            "diff": _compute_diff(before or {}, after or {})
        }

        return await AuditLogger.log(
            merchant_id=merchant_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
            **kwargs
        )

    @staticmethod
    async def log_reversible_action(
        merchant_id: str,
        action: AuditAction | str,
        entity_type: AuditEntityType | str,
        entity_id: str,
        reversal_type: str,
        original_state: dict,
        **kwargs
    ) -> tuple[AuditLog, ActionReversal]:
        """
        Log an action that can be reversed, with reversal instructions.

        Args:
            reversal_type: Type of reversal (e.g., "revert_price", "delete_discount")
            original_state: The state needed to reverse this action

        Returns:
            Tuple of (AuditLog, ActionReversal)
        """
        # First log the action
        audit_log = await AuditLogger.log_with_state(
            merchant_id=merchant_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            **kwargs
        )

        # Then create the reversal record
        async with async_session_maker() as session:
            reversal = ActionReversal(
                merchant_id=merchant_id,
                audit_log_id=audit_log.id,
                reversal_type=reversal_type,
                original_state=original_state,
                status="available"
            )
            session.add(reversal)
            await session.commit()
            await session.refresh(reversal)

            logger.info(
                f"Created reversible action: {action} on {entity_id} "
                f"with reversal type {reversal_type}"
            )

            return audit_log, reversal

    @staticmethod
    async def get_audit_trail(
        merchant_id: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        action: Optional[str] = None,
        actor_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[AuditLog]:
        """
        Query audit logs with filters.

        Returns:
            List of AuditLog entries matching the filters
        """
        async with async_session_maker() as session:
            query = select(AuditLog).where(AuditLog.merchant_id == merchant_id)

            if entity_type:
                query = query.where(AuditLog.entity_type == entity_type)
            if entity_id:
                query = query.where(AuditLog.entity_id == entity_id)
            if action:
                query = query.where(AuditLog.action == action)
            if actor_type:
                query = query.where(AuditLog.actor_type == actor_type)
            if start_date:
                query = query.where(AuditLog.created_at >= start_date)
            if end_date:
                query = query.where(AuditLog.created_at <= end_date)

            query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)

            result = await session.execute(query)
            return result.scalars().all()

    @staticmethod
    def set_context(
        user_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        auth_id: Optional[str] = None
    ):
        """
        Set context for subsequent audit log entries.

        Use this in middleware to set user context from requests.
        """
        if user_id:
            _current_user_id.set(user_id)
        if execution_id:
            _current_execution_id.set(execution_id)
        if auth_id:
            _current_auth_id.set(auth_id)

    @staticmethod
    def clear_context():
        """Clear all audit context."""
        _current_user_id.set(None)
        _current_execution_id.set(None)
        _current_auth_id.set(None)


def _compute_diff(before: dict, after: dict) -> dict:
    """Compute the difference between two state dicts."""
    diff = {}
    all_keys = set(before.keys()) | set(after.keys())

    for key in all_keys:
        before_val = before.get(key)
        after_val = after.get(key)
        if before_val != after_val:
            diff[key] = {"from": before_val, "to": after_val}

    return diff


# Convenience functions for common patterns
async def log_agent_action(
    merchant_id: str,
    agent_type: str,
    action: str,
    entity_type: str,
    entity_id: str,
    confidence: Optional[float] = None,
    metadata: Optional[dict] = None
) -> AuditLog:
    """Convenience function for logging agent actions."""
    meta = metadata or {}
    if confidence:
        meta["confidence"] = confidence

    return await AuditLogger.log(
        merchant_id=merchant_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_type="agent",
        actor_agent_type=agent_type,
        metadata=meta
    )


async def log_merchant_action(
    merchant_id: str,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    metadata: Optional[dict] = None
) -> AuditLog:
    """Convenience function for logging merchant actions."""
    return await AuditLogger.log(
        merchant_id=merchant_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_type="human",
        user_id=user_id,
        metadata=metadata
    )
