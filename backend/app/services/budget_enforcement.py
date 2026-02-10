# backend/app/services/budget_enforcement.py
"""
LLM Budget Enforcement Service.

Prevents merchants from exceeding their monthly LLM spending limits.
Prevents trial merchants from running up large bills.

Features:
- Plan-based budget limits
- Soft limit warnings at 80%
- Hard limit blocking at 100%
- Monthly reset on billing cycle
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Tuple, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Merchant, LLMUsageLog, InboxItem
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BudgetExceededError(Exception):
    """Raised when merchant exceeds LLM budget."""
    
    def __init__(self, message: str, current_usage: Decimal, limit: Decimal):
        self.current_usage = current_usage
        self.limit = limit
        super().__init__(message)


class BudgetEnforcementService:
    """
    Enforces LLM usage budgets per merchant.
    
    Budget tiers (defined in Merchant.monthly_llm_budget):
    - Trial: $50/month (default)
    - Growth: $500/month
    - Enterprise: Custom
    """
    
    # Plan-based default budgets (used if merchant.monthly_llm_budget not set)
    PLAN_BUDGETS = {
        "trial": Decimal("50.00"),
        "growth": Decimal("500.00"),
        "enterprise": Decimal("5000.00"),
    }
    
    SOFT_LIMIT_THRESHOLD = Decimal("0.80")  # Warn at 80%
    WARNING_COOLDOWN_HOURS = 24  # Don't spam warnings
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def check_budget(
        self,
        merchant_id: str,
        estimated_cost: Decimal
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if merchant has budget for operation.
        
        Args:
            merchant_id: Merchant to check
            estimated_cost: Estimated cost of the LLM operation
            
        Returns:
            (allowed, reason_if_blocked)
        """
        merchant = await self.session.get(Merchant, merchant_id)
        if not merchant:
            return False, "Merchant not found"
        
        budget_limit = self._get_budget_limit(merchant)
        
        # Calculate current usage
        current_usage = await self._get_current_month_usage(merchant_id)
        projected_usage = current_usage + estimated_cost
        
        # Check hard limit
        if projected_usage > budget_limit:
            logger.warning(
                f"Budget exceeded for merchant {merchant_id}: "
                f"${current_usage:.2f} + ${estimated_cost:.2f} > ${budget_limit:.2f}"
            )
            return False, (
                f"Monthly LLM budget exceeded. "
                f"Current: ${current_usage:.2f}, Limit: ${budget_limit:.2f}. "
                f"Upgrade plan or wait for billing cycle reset."
            )
        
        # Check soft limit (warn but allow)
        soft_limit = budget_limit * self.SOFT_LIMIT_THRESHOLD
        if projected_usage > soft_limit and current_usage <= soft_limit:
            await self._send_budget_warning(merchant, current_usage, budget_limit)
        
        return True, None
    
    async def check_and_raise(
        self,
        merchant_id: str,
        estimated_cost: Decimal
    ) -> None:
        """
        Check budget and raise BudgetExceededError if exceeded.
        
        Usage in LLMRouter:
            await budget_service.check_and_raise(merchant_id, estimated)
            # If we get here, operation is allowed
        """
        allowed, reason = await self.check_budget(merchant_id, estimated_cost)
        if not allowed:
            merchant = await self.session.get(Merchant, merchant_id)
            current = await self._get_current_month_usage(merchant_id)
            limit = self._get_budget_limit(merchant)
            raise BudgetExceededError(reason, current, limit)
    
    def _get_budget_limit(self, merchant: Merchant) -> Decimal:
        """Get budget limit for merchant."""
        # Use merchant's configured budget if set
        if merchant.monthly_llm_budget and merchant.monthly_llm_budget > 0:
            return merchant.monthly_llm_budget
        
        # Fall back to plan-based defaults
        return self.PLAN_BUDGETS.get(merchant.plan, self.PLAN_BUDGETS["trial"])
    
    async def _get_current_month_usage(self, merchant_id: str) -> Decimal:
        """
        Calculate LLM usage for current billing cycle.
        
        Uses the budget_reset_date from Merchant to determine cycle start.
        """
        merchant = await self.session.get(Merchant, merchant_id)
        cycle_start = merchant.budget_reset_date if merchant.budget_reset_date else self._get_cycle_start()
        
        result = await self.session.execute(
            select(func.coalesce(func.sum(LLMUsageLog.cost_usd), 0))
            .where(
                LLMUsageLog.merchant_id == merchant_id,
                LLMUsageLog.created_at >= cycle_start
            )
        )
        
        total = result.scalar()
        return Decimal(str(total)) if total else Decimal("0.00")
    
    def _get_cycle_start(self) -> datetime:
        """Get start of current billing cycle (first of month)."""
        now = datetime.utcnow()
        return datetime(now.year, now.month, 1)
    
    async def _send_budget_warning(
        self,
        merchant: Merchant,
        current_usage: Decimal,
        limit: Decimal
    ):
        """
        Send budget warning to merchant via InboxItem.
        
        Only sends one warning per 24 hours to avoid spam.
        """
        # Check for recent warning
        recent_warning = await self.session.execute(
            select(InboxItem).where(
                InboxItem.merchant_id == merchant.id,
                InboxItem.type == "budget_warning",
                InboxItem.created_at > datetime.utcnow() - timedelta(hours=self.WARNING_COOLDOWN_HOURS)
            ).limit(1)
        )
        
        if recent_warning.scalar_one_or_none():
            return  # Already warned recently
        
        # Create warning inbox item
        warning = InboxItem(
            merchant_id=merchant.id,
            type="budget_warning",
            status="pending",
            agent_type="system",
            risk_level="low",
            proposal_data={
                "title": "Budget Alert: 80% Usage",
                "message": (
                    f"You've used ${current_usage:.2f} of your ${limit:.2f} monthly LLM budget. "
                    f"Consider upgrading your plan to avoid service interruption."
                ),
                "current_usage": float(current_usage),
                "limit": float(limit),
                "percentage": float(current_usage / limit * 100),
            }
        )
        self.session.add(warning)
        await self.session.commit()
        
        logger.info(f"Budget warning sent to merchant {merchant.id}")
    
    async def get_usage_summary(self, merchant_id: str) -> dict:
        """Get budget usage summary for dashboard display."""
        merchant = await self.session.get(Merchant, merchant_id)
        if not merchant:
            return {"error": "Merchant not found"}
        
        budget_limit = self._get_budget_limit(merchant)
        current_usage = await self._get_current_month_usage(merchant_id)
        
        return {
            "current_usage": float(current_usage),
            "budget_limit": float(budget_limit),
            "percentage_used": float(current_usage / budget_limit * 100) if budget_limit > 0 else 0,
            "remaining": float(budget_limit - current_usage),
            "plan": merchant.plan,
            "reset_date": merchant.budget_reset_date.isoformat() if merchant.budget_reset_date else None,
        }
    
    async def reset_monthly_budget(self, merchant_id: str) -> bool:
        """
        Reset budget for new billing cycle.
        
        Called by scheduled task on billing date.
        """
        merchant = await self.session.get(Merchant, merchant_id)
        if not merchant:
            return False
        
        merchant.current_llm_spend = Decimal("0.00")
        merchant.budget_reset_date = datetime.utcnow()
        await self.session.commit()
        
        logger.info(f"Budget reset for merchant {merchant_id}")
        return True


def estimate_llm_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int
) -> Decimal:
    """
    Estimate LLM cost before making a call.
    
    Pricing (as of Jan 2024):
    - Claude 3.5 Sonnet: $3/1M input, $15/1M output
    - GPT-4o: $2.5/1M input, $10/1M output
    - GPT-4o-mini: $0.15/1M input, $0.6/1M output
    - Gemini 1.5 Pro: $1.25/1M input, $5/1M output
    """
    pricing = {
        ("anthropic", "claude-3-5-sonnet"): {"input": Decimal("0.000003"), "output": Decimal("0.000015")},
        ("anthropic", "claude-3-5-sonnet-20241022"): {"input": Decimal("0.000003"), "output": Decimal("0.000015")},
        ("openai", "gpt-4o"): {"input": Decimal("0.0000025"), "output": Decimal("0.00001")},
        ("openai", "gpt-4o-mini"): {"input": Decimal("0.00000015"), "output": Decimal("0.0000006")},
        ("google", "gemini-1.5-pro"): {"input": Decimal("0.00000125"), "output": Decimal("0.000005")},
    }
    
    # Default pricing for unknown models
    default_pricing = {"input": Decimal("0.000003"), "output": Decimal("0.000015")}
    
    rates = pricing.get((provider.lower(), model.lower()), default_pricing)
    
    cost = (
        Decimal(str(input_tokens)) * rates["input"] +
        Decimal(str(output_tokens)) * rates["output"]
    )
    
    return cost


def estimate_prompt_cost(
    provider: str,
    model: str,
    prompt_length: int
) -> Decimal:
    """
    Rough estimate based on prompt character length.
    
    Assumes:
    - ~4 characters per token
    - Output is ~50% of input length
    """
    estimated_input_tokens = prompt_length // 4
    estimated_output_tokens = estimated_input_tokens // 2
    
    return estimate_llm_cost(provider, model, estimated_input_tokens, estimated_output_tokens)
