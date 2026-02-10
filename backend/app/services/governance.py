import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ActionReversal, AuditLog

logger = logging.getLogger(__name__)

class GovernanceService:
    """
    Handles state capture and reversal (rollback) of agent actions.
    Ensures that every 'Act' can be matched by an 'Undo'.
    """
    
    def __init__(self, db: AsyncSession, merchant_id: str):
        self.db = db
        self.merchant_id = merchant_id

    async def record_reversal_point(
        self, 
        audit_log_id: str, 
        reversal_type: str, 
        original_state: Dict[str, Any]
    ) -> ActionReversal:
        """
        Records the current state of an entity before it is modified.
        
        Args:
            audit_log_id: The ID of the audit log entry for the action being taken.
            reversal_type: Type of reversal (e.g., 'remove_klaviyo_campaign').
            original_state: JSON blob containing enough info to undo the action.
        """
        reversal = ActionReversal(
            merchant_id=self.merchant_id,
            audit_log_id=audit_log_id,
            reversal_type=reversal_type,
            original_state=original_state,
            status="available"
        )
        self.db.add(reversal)
        await self.db.flush()
        
        logger.info(f"🛡️ Registered reversal point for audit_log {audit_log_id} type {reversal_type}")
        return reversal

    async def execute_rollback(self, reversal_id: str) -> bool:
        """
        Executes the rollback logic based on the recorded state.
        
        This is a high-level dispatcher that calls specific integration 
        reversal logic (e.g., calling Shopify API to delete a discount).
        """
        from sqlalchemy import select
        result = await self.db.execute(
            select(ActionReversal).where(
                ActionReversal.id == reversal_id,
                ActionReversal.merchant_id == self.merchant_id
            )
        )
        reversal = result.scalar_one_or_none()
        
        if not reversal or reversal.status != "available":
            logger.warning(f"Rollback {reversal_id} not available or not found.")
            return False

        try:
            success = False
            if reversal.reversal_type == "delete_klaviyo_campaign":
                success = await self._rollback_klaviyo_campaign(reversal.original_state)
            elif reversal.reversal_type == "revert_shopify_discount":
                success = await self._rollback_shopify_discount(reversal.original_state)
            else:
                logger.error(f"Unknown reversal type: {reversal.reversal_type}")
                reversal.status = "failed"
                reversal.reversal_error = "Unknown reversal type"
            
            if success:
                reversal.status = "executed"
                reversal.executed_at = datetime.utcnow()
                logger.info(f"✅ Rollback {reversal_id} executed successfully.")
            else:
                reversal.status = "failed"
                reversal.reversal_error = "Dispatcher failed to execute reversal logic"
                
            await self.db.commit()
            return success
            
        except Exception as e:
            logger.error(f"❌ Rollback {reversal_id} failed: {e}")
            reversal.status = "failed"
            reversal.reversal_error = str(e)
            await self.db.commit()
            return False

    async def _rollback_klaviyo_campaign(self, state: Dict) -> bool:
        """Klaviyo-specific rollback: delete the created campaign."""
        campaign_id = state.get('campaign_id')
        if not campaign_id: return False
        
        # In a real system, we'd fetch credentials and call the Klaviyo API
        logger.info(f"Mocking Klaviyo campaign deletion for: {campaign_id}")
        return True

    async def _rollback_shopify_discount(self, state: Dict) -> bool:
        """Shopify-specific rollback: delete the price rule."""
        price_rule_id = state.get('price_rule_id')
        if not price_rule_id: return False
        
        logger.info(f"Mocking Shopify discount deletion for: {price_rule_id}")
        return True
