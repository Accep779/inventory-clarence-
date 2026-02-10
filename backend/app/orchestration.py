"""
Task Orchestration Layer
========================

Defines the unified task execution strategy for Cephly.

ARCHITECTURE DECISION:
- Temporal is the PRIMARY execution engine for all background work
- Celery has been REMOVED (was previously mocked, now completely removed)
- Simple one-off tasks use direct async function calls
- Scheduled tasks use Temporal schedules
- Long-running workflows use Temporal workflows

Migration Status:
✅ Campaign Execution -> Temporal Workflow
✅ Quick Scan -> Temporal Workflow
✅ Seasonal Scan -> Temporal Workflow
🔄 Initial Sync -> Being migrated to Temporal Activity
🔄 Observer Analysis -> Being migrated to Temporal Activity
🔄 Matchmaker -> Being migrated to Temporal Activity
"""

import asyncio
import logging
from typing import Callable, Any
from functools import wraps

from temporalio.client import Client
from temporalio.runtime import Runtime

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# =============================================================================
# TEMPORAL CLIENT (Lazy Initialization)
# =============================================================================

_temporal_client: Client | None = None


async def get_temporal_client() -> Client:
    """Get or create Temporal client connection."""
    global _temporal_client
    if _temporal_client is None:
        temporal_url = settings.TEMPORAL_URL if hasattr(settings, 'TEMPORAL_URL') else "localhost:7233"
        _temporal_client = await Client.connect(temporal_url, namespace="default")
        logger.info(f"Connected to Temporal at {temporal_url}")
    return _temporal_client


# =============================================================================
# TASK DECORATORS
# =============================================================================

def temporal_activity(name: str = None):
    """
    Decorator for Temporal activities.

    Activities are:
    - Idempotent (safe to retry)
    - Short-lived (seconds to minutes)
    - Single-purpose (one thing well)
    """
    def decorator(func: Callable) -> Callable:
        func._temporal_activity = True
        func._activity_name = name or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Log activity execution
            logger.info(f"Executing activity: {func._activity_name}")
            try:
                result = await func(*args, **kwargs)
                logger.info(f"Activity completed: {func._activity_name}")
                return result
            except Exception as e:
                logger.error(f"Activity failed: {func._activity_name} - {e}")
                raise

        return wrapper
    return decorator


def temporal_workflow(name: str = None):
    """
    Decorator for Temporal workflows.

    Workflows are:
    - Durable (survive process restarts)
    - Long-running (minutes to days)
    - Orchestration-focused (coordinate activities)
    """
    def decorator(cls):
        cls._temporal_workflow = True
        cls._workflow_name = name or cls.__name__
        return cls
    return decorator


def background_task(name: str = None, queue: str = "default"):
    """
    Decorator for simple background tasks.

    These tasks are:
    - Fire-and-forget
    - Non-critical (can fail silently)
    - Short-lived (seconds)

    For critical work, use Temporal activities/workflows instead.
    """
    def decorator(func: Callable) -> Callable:
        task_name = name or func.__name__

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger.debug(f"Running background task: {task_name}")
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Background task failed (non-critical): {task_name} - {e}")
                # Don't re-raise - background tasks are best-effort

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Fire and forget for sync contexts
            asyncio.create_task(async_wrapper(*args, **kwargs))

        # Attach both versions
        func.delay = sync_wrapper
        func.run_async = async_wrapper
        func._task_name = task_name
        func._task_queue = queue

        return func
    return decorator


# =============================================================================
# TASK REGISTRY
# =============================================================================

class TaskRegistry:
    """
    Central registry for all tasks.

    Used by the worker to discover and register activities/workflows.
    """

    def __init__(self):
        self.activities: dict[str, Callable] = {}
        self.workflows: dict[str, Any] = {}
        self.background_tasks: dict[str, Callable] = {}

    def register_activity(self, func: Callable):
        """Register a Temporal activity."""
        name = getattr(func, '_activity_name', func.__name__)
        self.activities[name] = func
        logger.debug(f"Registered activity: {name}")
        return func

    def register_workflow(self, cls):
        """Register a Temporal workflow."""
        name = getattr(cls, '_workflow_name', cls.__name__)
        self.workflows[name] = cls
        logger.debug(f"Registered workflow: {name}")
        return cls

    def register_background_task(self, func: Callable):
        """Register a background task."""
        name = getattr(func, '_task_name', func.__name__)
        self.background_tasks[name] = func
        logger.debug(f"Registered background task: {name}")
        return func

    def get_all_activities(self) -> list[Callable]:
        """Get all registered activities for worker startup."""
        return list(self.activities.values())

    def get_all_workflows(self) -> list[Any]:
        """Get all registered workflows for worker startup."""
        return list(self.workflows.values())


# Global registry instance
registry = TaskRegistry()


# =============================================================================
# EXECUTION HELPERS
# =============================================================================

async def execute_workflow(workflow_name: str, args: tuple = (), kwargs: dict = None, task_queue: str = "default"):
    """
    Execute a Temporal workflow.

    Args:
        workflow_name: Name of the registered workflow
        args: Positional arguments for the workflow
        kwargs: Keyword arguments for the workflow
        task_queue: Temporal task queue to use

    Returns:
        Workflow result
    """
    client = await get_temporal_client()

    workflow_cls = registry.workflows.get(workflow_name)
    if not workflow_cls:
        raise ValueError(f"Workflow not found: {workflow_name}")

    result = await client.execute_workflow(
        workflow_cls.run,
        *args,
        **(kwargs or {}),
        id=f"{workflow_name}-{datetime.utcnow().isoformat()}",
        task_queue=task_queue
    )

    return result


async def start_background_task(task_name: str, *args, **kwargs):
    """
    Start a background task.

    For non-critical, fire-and-forget work.
    """
    task_func = registry.background_tasks.get(task_name)
    if not task_func:
        raise ValueError(f"Background task not found: {task_name}")

    # Fire and forget
    asyncio.create_task(task_func(*args, **kwargs))


# =============================================================================
# DEPRECATION HELPERS
# =============================================================================

class RemovedCeleryError(Exception):
    """Raised when Celery-specific code is called."""
    pass


def celery_removed_warning(func_name: str):
    """Log a warning about removed Celery functionality."""
    logger.error(
        f"CELERY REMOVED: {func_name} was called but Celery has been removed. "
        f"Use Temporal workflows/activities instead. "
        f"See app/orchestration.py for migration guide."
    )
    raise RemovedCeleryError(
        f"Celery has been removed. Migrate {func_name} to Temporal. "
        f"See app/orchestration.py for details."
    )


# Legacy Celery mock for runtime safety during migration
celery_app = None  # Completely removed - will cause AttributeError if used
