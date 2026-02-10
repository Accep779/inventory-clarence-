import asyncio
import uuid
from temporalio.client import Client

# Mock Data for Testing
TEST_PAYLOAD = {
    "merchant_id": "test_merchant_123",
    "proposal_id": "test_proposal_456"
    # Logic inside activities will likely fail DB lookups for these fake IDs
    # But checking if the Workflow STARTS and Activities FAIL is a valid test of durability!
}

async def main():
    # Connect to server
    client = await Client.connect("localhost:7233")

    # Run workflow
    handle = await client.start_workflow(
        "CampaignWorkflow",
        TEST_PAYLOAD,
        id=f"campaign-test-{uuid.uuid4()}",
        task_queue="execution-agent-queue",
    )

    print(f"✅ Workflow started! run_id: {handle.run_id}")
    print(f"👉 Check UI: http://localhost:8233/namespaces/default/workflows/{handle.id}/{handle.run_id}/history")

    # Optional: Wait for result (will raise error if workflow fails)
    # result = await handle.result()
    # print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
