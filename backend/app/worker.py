"""
Temporal Worker - Unified Background Task Processing

This worker runs all background tasks using Temporal:
- Workflows: Long-running, durable processes (campaigns, scans)
- Activities: Short, idempotent units of work
- Background Tasks: Simple, fire-and-forget operations

Celery has been REMOVED. All task execution goes through Temporal.
"""

import asyncio
import logging
from datetime import datetime

from temporalio.client import Client
from temporalio.worker import Worker

from app.config import get_settings
from app.orchestration import registry, get_temporal_client

# Import and register workflows
from app.workflows.campaign import CampaignWorkflow
from app.workflows.scan import QuickScanWorkflow, SeasonalScanWorkflow

registry.register_workflow(CampaignWorkflow)
registry.register_workflow(QuickScanWorkflow)
registry.register_workflow(SeasonalScanWorkflow)

# Import and register activities
from app.activities.campaign import (
    check_safety_pause, mark_campaign_failed, simulate_execution,
    check_requires_auth, initiate_ciba_auth, claim_proposal_execution,
    create_campaign_record, send_klaviyo_campaign, send_twilio_campaign,
    verify_and_update_status
)
from app.activities.scan import ScanActivities

# Register all activities
scan_activities = ScanActivities()
registry.register_activity(check_safety_pause)
registry.register_activity(mark_campaign_failed)
registry.register_activity(simulate_execution)
registry.register_activity(check_requires_auth)
registry.register_activity(initiate_ciba_auth)
registry.register_activity(claim_proposal_execution)
registry.register_activity(create_campaign_record)
registry.register_activity(send_klaviyo_campaign)
registry.register_activity(send_twilio_campaign)
registry.register_activity(verify_and_update_status)
registry.register_activity(scan_activities.quick_scan_product_batch)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


async def main():
    """Start the Temporal worker with all registered workflows and activities."""
    client = await get_temporal_client()
    logger.info("Connected to Temporal Server")

    # Get all registered workflows and activities
    workflows = registry.get_all_workflows()
    activities = registry.get_all_activities()

    logger.info(f"Starting worker with {len(workflows)} workflows and {len(activities)} activities")

    worker = Worker(
        client,
        task_queue="execution-agent-queue",
        workflows=workflows,
        activities=activities,
    )

    logger.info("Worker started. Waiting for tasks...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
