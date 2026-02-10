import asyncio
from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow, ScheduleSpec, ScheduleIntervalSpec, ScheduleCalendarSpec
from app.workflows.scan import SeasonalScanWorkflow

async def main():
    client = await Client.connect("localhost:7233")
    
    # Define the schedule
    # Run every Sunday at 2 AM
    
    try:
        await client.create_schedule(
            "weekly-seasonal-scan-schedule",
            Schedule(
                action=ScheduleActionStartWorkflow(
                    SeasonalScanWorkflow.run,
                    {"merchant_id": "all"}, # Placeholder logic would need to scan all merchants
                    id="seasonal-scan-job",
                    task_queue="execution-agent-queue",
                ),
                spec=ScheduleSpec(
                    calendars=[ScheduleCalendarSpec(day_of_week=[0], hour=[2])],
                ),
            ),
        )
        print("✅ Schedule 'weekly-seasonal-scan-schedule' created.")
    except Exception as e:
        print(f"⚠️ Failed to create schedule (might exist): {e}")

if __name__ == "__main__":
    asyncio.run(main())
