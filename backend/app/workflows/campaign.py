from datetime import timedelta
from typing import Dict, Optional, List
from temporalio import workflow
from temporalio.common import RetryPolicy

# Import Activities (we will define these next)
# from app.activities.campaign import ...

@workflow.defn
class CampaignWorkflow:
    @workflow.run
    async def run(self, input_data: Dict) -> Dict:
        """
        Durable Campaign Execution Workflow.
        Replaces ExecutionAgent.execute_campaign logic.
        
        Args:
            input_data: {
                'merchant_id': str,
                'proposal_id': str
            }
        """
        merchant_id = input_data['merchant_id']
        proposal_id = input_data['proposal_id']
        
        # 0. SAFETY: Emergency Pause Check (Activity)
        is_paused = await workflow.execute_activity(
            "check_safety_pause",
            args=[merchant_id],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        if is_paused:
            # We can log failure via activity or return blocked status
            await workflow.execute_activity(
                "mark_campaign_failed",
                args=[merchant_id, proposal_id, "Emergency Pause is Active"],
                start_to_close_timeout=timedelta(seconds=10)
            )
            return {'status': 'blocked', 'reason': 'safety_pause'}

        # 1. PREDICT: Simulation (Activity)
        simulation = await workflow.execute_activity(
            "simulate_execution",
            args=[merchant_id, proposal_id],
            start_to_close_timeout=timedelta(minutes=2), # Simulation might take time
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        if simulation.get('blocked', False):
            await workflow.execute_activity(
                "mark_campaign_failed",
                args=[merchant_id, proposal_id, simulation['reason']],
                start_to_close_timeout=timedelta(seconds=10)
            )
            return {'status': 'blocked', 'reason': simulation['reason']}

        # 2. AUTHORIZE: CIBA Async Auth (Activity + Signal Wait?)
        # For now we will keep it simple: assume if CIBA is needed, we do it via Activity waiting?
        # Or better: Signal.
        # Let's check needs_auth first
        needs_auth = await workflow.execute_activity(
            "check_requires_auth",
            args=[merchant_id, proposal_id, simulation],
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if needs_auth:
             # Request Auth
             await workflow.execute_activity(
                 "initiate_ciba_auth",
                 args=[merchant_id, proposal_id, simulation],
                 start_to_close_timeout=timedelta(minutes=1)
             )
             
             # Wait for Signal "ciba_approved" or "ciba_denied"
             # This makes the workflow pause DURABLY for days if needed
             # Implementation TODO: signals
             pass 

        # 3. ACT: Execute Campaign (Activity)
        # We assume the "Execute Internal" big block is broken down or kept as one activity for now
        # To gain granular retry on Klaviyo vs Twilio, best to split them.
        
        # Lock / Claim Proposal
        claim_result = await workflow.execute_activity(
            "claim_proposal_execution",
            args=[merchant_id, proposal_id],
            start_to_close_timeout=timedelta(seconds=10)
        )
        if claim_result.get('status') != 'success':
            return claim_result # already executed etc

        # Parse Campaign Data (Activity? or just part of claim result used here?)
        proposal_data = claim_result.get('data', {})
        
        # Execute Channels in Parallel or Sequence
        # Using parallel usage of asyncio.gather equivalent in Temporal is mostly just executing activities
        
        # Creating Campaign Record
        campaign_id = await workflow.execute_activity(
            "create_campaign_record",
            args=[merchant_id, proposal_data],
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # Run Channels
        # We can use execute_activity mainly
        # Note: In a real migration we'd split Klaviyo and Twilio into separate activities
        # so failure in one doesn't retry the other if they succeeded.
        
        results = await asyncio.gather(
            workflow.execute_activity(
                "send_klaviyo_campaign",
                args=[merchant_id, campaign_id, proposal_data],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=3)
            ),
            workflow.execute_activity(
                "send_twilio_campaign",
                args=[merchant_id, campaign_id, proposal_data, simulation],
                start_to_close_timeout=timedelta(minutes=10), # specific staggering logic might be inside
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
        )
        
        klaviyo_res, twilio_res = results
        
        # 4. VERIFY & UPDATE
        verification = await workflow.execute_activity(
            "verify_and_update_status",
            args=[merchant_id, proposal_id, campaign_id, klaviyo_res, twilio_res],
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return verification

