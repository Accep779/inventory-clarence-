# app/services/governor.py
"""
Governor Service
================
Manages AI autonomy and determines if actions can be auto-executed.

EXTRACTED FROM: Cephly architecture
"""

import logging
from typing import Dict, Any, Optional, Tuple
from sqlalchemy import select, func
from app.database import async_session_maker
from app.models import InboxItem, Merchant

logger = logging.getLogger(__name__)

class AutonomyDecision:
    AUTO_APPROVE = "AUTO_APPROVE"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"

class GovernorService:
    """
    Evaluates if a proposal should be automatically executed or requires human approval.
    """
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id

    async def evaluate_autonomy(
        self, 
        skill_name: str, 
        risk_level: str, 
        confidence: Optional[float] = None
    ) -> str:
        """
        [ENGINE #1]: Autonomous Governor with Risk Matrix.
        """
        async with async_session_maker() as session:
            # 1. NEW: Check Risk Matrix Policy
            from app.models import RiskPolicy
            policy_stmt = select(RiskPolicy).where(
                RiskPolicy.agent_type == skill_name,
                RiskPolicy.risk_level == risk_level
            )
            policy = (await session.execute(policy_stmt)).scalars().first()
            
            if policy and policy.requires_approval:
                return AutonomyDecision.REQUIRE_APPROVAL

            # 2. Fetch merchant settings
            merchant = (await session.execute(
                select(Merchant).where(Merchant.id == self.merchant_id)
            )).scalars().first()
            
            # 3. Critical risk check (Hardcoded safety)
            if risk_level == 'critical':
                return AutonomyDecision.REQUIRE_APPROVAL
            
            # 4. Calibration check (Historical approvals)
            count_result = await session.execute(
                select(func.count(InboxItem.id))
                .where(
                    InboxItem.merchant_id == self.merchant_id,
                    InboxItem.status.in_(['approved', 'executed'])
                )
            )
            total_approvals = count_result.scalar() or 0
            
            calibration_threshold = merchant.governor_calibration_threshold or 50
            if total_approvals < calibration_threshold:
                return AutonomyDecision.REQUIRE_APPROVAL
            
            # 5. Trust Score check
            history_result = await session.execute(
                select(InboxItem.status)
                .where(
                    InboxItem.merchant_id == self.merchant_id,
                    InboxItem.agent_type == skill_name
                )
            )
            history = history_result.scalars().all()
            
            if not history:
                return AutonomyDecision.REQUIRE_APPROVAL
            
            approved_count = sum(1 for status in history if status in ['approved', 'executed'])
            total_count = len(history)
            trust_score = approved_count / total_count if total_count > 0 else 0
            
            # 6. Final Decision using Policy or Defaults
            min_confidence = policy.min_confidence if policy else 0.95
            min_trust = policy.min_trust_score if policy else 0.92
            
            if confidence and confidence >= min_confidence and trust_score >= min_trust:
                return AutonomyDecision.AUTO_APPROVE
            
            return AutonomyDecision.REQUIRE_APPROVAL

    async def get_status_summary(self, skill_name: str, risk_level: str) -> dict:
        """ Returns status for UI components. """
        # Implementation similar to evaluate_autonomy but returns metadata
        async with async_session_maker() as session:
            merchant = (await session.execute(select(Merchant).where(Merchant.id == self.merchant_id))).scalars().first()
            
            count_result = await session.execute(
                select(func.count(InboxItem.id))
                .where(InboxItem.merchant_id == self.merchant_id, InboxItem.status.in_(['approved', 'executed']))
            )
            total_approvals = count_result.scalar() or 0
            
            target = merchant.governor_calibration_threshold or 50
            
            return {
                "is_calibrated": total_approvals >= target,
                "progress": total_approvals,
                "target": target,
                "risk_level": risk_level
            }
    
    # =========================================================================
    # SCOPE-BASED AUTHORIZATION (Auth0 Pattern)
    # =========================================================================
    
    async def check_scope_authorization(
        self, 
        agent_type: str, 
        required_scopes: list[str],
        context: dict = None
    ) -> tuple[bool, list[str]]:
        """
        Check if an agent has the required scopes for an operation.
        
        Args:
            agent_type: The type of agent (execution, strategy, etc.)
            required_scopes: List of scope strings required for the operation
            context: Optional context for conditional scope evaluation
            
        Returns:
            Tuple of (is_authorized, missing_scopes)
        """
        from app.services.scopes import CephlyScopes, check_scopes
        from app.models import MerchantScopeGrant
        
        context = context or {}
        
        # 1. Get default scopes for agent type
        default_scopes = CephlyScopes.get_default_scopes_for_agent(agent_type)
        
        # 2. Get merchant-specific grants
        granted_scopes = await self.get_granted_scopes(agent_type)
        
        # 3. Combine default + granted
        effective_scopes = default_scopes.union(granted_scopes)
        
        # 4. Check required vs effective
        is_authorized, missing = check_scopes(required_scopes, list(effective_scopes))
        
        if not is_authorized:
            logger.info(
                f"🚫 Scope authorization failed for {agent_type}: "
                f"missing {missing}"
            )
        
        return is_authorized, missing
    
    async def get_granted_scopes(self, agent_type: str) -> set[str]:
        """
        Get all scopes granted to an agent type by this merchant.
        """
        from app.models import MerchantScopeGrant
        
        async with async_session_maker() as session:
            result = await session.execute(
                select(MerchantScopeGrant).where(
                    MerchantScopeGrant.merchant_id == self.merchant_id,
                    MerchantScopeGrant.agent_type == agent_type,
                    MerchantScopeGrant.is_active == True
                )
            )
            grants = result.scalars().all()
            
            return {g.scope for g in grants}
    
    async def check_conditional_scope(
        self,
        scope: str,
        agent_type: str,
        context: dict
    ) -> bool:
        """
        Check if a conditional scope grant allows this specific operation.
        
        Example: discounts:moderate with condition {"max_discount": 0.30}
        """
        from app.models import MerchantScopeGrant
        
        async with async_session_maker() as session:
            stmt = select(MerchantScopeGrant).where(
                    MerchantScopeGrant.merchant_id == self.merchant_id,
                    MerchantScopeGrant.agent_type == agent_type,
                    MerchantScopeGrant.scope == scope,
                    MerchantScopeGrant.is_active == True
                )
            grant = (await session.execute(stmt)).scalars().first()
            
            if not grant:
                return False
            
            # No conditions = always allowed
            if not grant.conditions:
                return True
            
            # Evaluate conditions
            conditions = grant.conditions
            
            # Max discount check
            if "max_discount" in conditions:
                discount = context.get("discount", 0)
                if discount > conditions["max_discount"]:
                    logger.info(
                        f"Conditional scope failed: discount {discount} > "
                        f"max {conditions['max_discount']}"
                    )
                    return False
            
            # Max daily spend check
            if "max_daily_spend" in conditions:
                daily_spend = context.get("daily_spend", 0)
                if daily_spend > conditions["max_daily_spend"]:
                    return False
            
            # Allowed segments check
            if "allowed_segments" in conditions:
                segments = context.get("segments", [])
                allowed = set(conditions["allowed_segments"])
                if not set(segments).issubset(allowed):
                    return False
            
            return True

