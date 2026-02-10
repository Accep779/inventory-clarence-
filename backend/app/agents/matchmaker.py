# backend/app/agents/matchmaker.py
"""
Matchmaker Agent
================

The "Connectors" of the system. Responsible for matching specific stock risks
to the customer segments most likely to clear them.

Implements world-class patterns:
1. Dual Memory (Historical response rates)
2. Strategic Affinity Reasoning (LLM-driven matching)
3. Fatigue Awareness (Reasoning about recent reach-outs)
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from decimal import Decimal

from sqlalchemy import select, desc, func
from app.database import async_session_maker
from app.models import Customer, AgentThought, Campaign
from app.services.memory import MemoryService
# from app.services.thought_logger import ThoughtLogger # Removed direct dependency
from app.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)

class MatchmakerAgent:
    """
    Transforms hardcoded segment matching into intelligent affinity reasoning.
    """
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self.memory = MemoryService(merchant_id)
        self.router = LLMRouter()
        self.agent_type = "matchmaker"
        self._api_token = None

    async def _log_thought(self, **kwargs):
        """Helper to log thoughts via Internal API."""
        if not self._api_token: await self._authenticate()
        
        import aiohttp
        headers = {"Authorization": f"Bearer {self._api_token}"}
        
        # Map kwargs to API schema
        payload = {
            "agent_type": self.agent_type,
            "thought_type": kwargs.get("thought_type", "info"),
            "summary": kwargs.get("summary", ""),
            "detailed_reasoning": kwargs.get("detailed_reasoning", {}),
            "confidence_score": float(kwargs.get("confidence_score", 1.0)),
            "step_number": kwargs.get("step_number", 1),
            "execution_id": kwargs.get("execution_id"),
            "product_id": kwargs.get("detailed_reasoning", {}).get("product_id") or kwargs.get("product_id")
        }
        
        try:
            async with aiohttp.ClientSession() as http:
                await http.post(
                    "http://localhost:8000/internal/agents/thoughts",
                    json=payload,
                    headers=headers
                )
        except Exception as e:
            logger.error(f"Failed to log thought via API: {e}")

    async def get_optimal_audience(
        self, 
        product_data: Dict[str, Any], 
        strategy: str,
        session
    ) -> Dict[str, Any]:
        """
        Reason about the best audience for a specific product and strategy.
        
        Returns:
            Dict containing:
                - target_segments: List[str]
                - reasoning: str
                - confidence: float
                - estimated_reach: int
        """
        # 1. GATHER: Get segment sizes and current health
        segments = await self._get_segment_stats(session)
        
        # 2. RECALL: Past performance of this strategy/product type
        past_performance = await self.memory.recall_campaign_outcomes(
            product_id=product_data.get('id'), 
            limit=3
        )
        
        # 3. REASON: LLM-driven Strategic Affinity
        matching = await self._reason_about_matching(
            product_data, 
            strategy, 
            segments, 
            past_performance
        )
        
        # 4. ENRICH: Calculate estimated reach from non-fatigued segments
        matching['estimated_reach'] = sum(segments.get(s, 0) for s in matching.get('target_segments', []))

        # 5. LOG: Transparent reasoning
        # 5. LOG: Transparent reasoning
        await self._log_thought(
            thought_type="matching",
            summary=f"Matched '{strategy}' to {', '.join(matching['target_segments'])}. Reach: {matching['estimated_reach']} customers.",
            detailed_reasoning={
                "strategy": strategy,
                "segments": segments,
                "reasoning": matching["reasoning"],
                "reach": matching['estimated_reach'],
                "past_performance_count": len(past_performance)
            },
            product_id=product_data.get('id')
        )
        
        return matching

    async def _get_segment_stats(self, session) -> Dict[str, int]:
        """Fetch current count of active, non-fatigued customers in each RFM segment."""
        from datetime import timedelta
        from app.models import TouchLog
        
        fatigue_cutoff = datetime.utcnow() - timedelta(days=5)
        counts = {}
        
        # 1. Get totals per segment in a single query
        total_stmt = select(Customer.rfm_segment, func.count(Customer.id)).where(
            Customer.merchant_id == self.merchant_id
        ).group_by(Customer.rfm_segment)
        total_res = await session.execute(total_stmt)
        totals = {row[0]: row[1] for row in total_res.all()}
        
        # 2. Get fatigue counts per segment in a single query
        fatigue_stmt = select(Customer.rfm_segment, func.count(func.distinct(Customer.id))).join(
            TouchLog, TouchLog.customer_id == Customer.id
        ).where(
            Customer.merchant_id == self.merchant_id,
            TouchLog.created_at >= fatigue_cutoff
        ).group_by(Customer.rfm_segment)
        fatigue_res = await session.execute(fatigue_stmt)
        fatigue_counts = {row[0]: row[1] for row in fatigue_res.all()}
        
        counts = {}
        for segment in ["champions", "loyal", "at_risk", "lapsed", "lost", "potential"]:
            total = totals.get(segment, 0)
            fatigued = fatigue_counts.get(segment, 0)
            counts[segment] = max(0, total - fatigued)
            
        return counts

    async def _reason_about_matching(
        self, 
        product: Dict, 
        strategy: str, 
        segments: Dict, 
        past_perf: List
    ) -> Dict:
        """Use LLM to find the strategic 'sweet spot' for matching."""
        
        prompt = f"""Match this clearance strategy to the best customer segments.

STRATEGY: {strategy}
PRODUCT: {product.get('title')} ({product.get('product_type')})
DISCOUNT LEVEL: {product.get('suggested_discount', 'N/A')}

AVAILABLE SEGMENTS (Size):
{json.dumps(segments, indent=2)}

PAST CAMPAIGN PERFORMANCE:
{json.dumps(past_perf, indent=2) if past_perf else "No data for this specific product."}

Logic Guidelines:
1. Champions & Loyal: Value exclusivity and early access over deep discounts.
2. At-Risk: Need a reason to come back (Moderate discounts).
3. Lapsed & Lost: Need extreme "Shock & Awe" discounts (Aggressive Liquidation).
4. Do not target exhausted segments if past performance shows low CTR (<1%).

Respond with JSON:
{{
    "target_segments": ["segment1", "segment2"],
    "reasoning": "High-level strategic rationale",
    "confidence": 0.0-1.0,
    "audience_description": "Human readable description for the campaign"
}}"""

        try:
            response = await self.router.complete(
                task_type="strategy_generation",
                system_prompt="You are a Retail Audience Strategist. Match products to segments that will actually buy them.",
                user_prompt=prompt,
                merchant_id=self.merchant_id
            )
            
            content = response['content'].strip()
            if '```' in content:
                content = content.split('```')[1].replace('json', '')
            
            return json.loads(content)
        except Exception as e:
            logger.error(f"Matchmaker reasoning failed: {e}")
            # Fallback to legacy hardcoded logic
            from app.tasks.matchmaker import MatchmakerAgent as LegacyMatchmaker
            legacy = LegacyMatchmaker(self.merchant_id)
            fallback_segments = await legacy.get_audience_for_strategy(strategy)
            return {
                "target_segments": fallback_segments,
                "reasoning": "Deterministic fallback used due to reasoning error.",
                "confidence": 0.5,
                "audience_description": f"Targeting {', '.join(fallback_segments)} based on standard RFM mapping."
            }
            
    async def _authenticate(self):
        """[HARDENING] Authenticates with Internal API using Vaulted Credentials."""
        if self._api_token: return
        import aiohttp
        from app.services.identity import IdentityService
        from app.database import async_session_maker
        async with async_session_maker() as db:
            identity_service = IdentityService(db, self.merchant_id)
            creds = await identity_service.get_agent_credentials("matchmaker")
        if not creds:
             logger.error("Failed to fetch Matchmaker credentials")
             return
        async with aiohttp.ClientSession() as http:
            async with http.post("http://localhost:8000/internal/agents/auth", json=creds) as resp:
                if resp.status == 200:
                     self._api_token = (await resp.json())['access_token']
                else:
                     logger.error(f"Matchmaker Auth Failed: {await resp.text()}")

    async def run_daily_segmentation(self):
        """
        Analyzes customer base and pushes segment stats to the central brain.
        Now uses Secure Internal API.
        """
        async with async_session_maker() as session:
            # 1. Calculate Stats (Read-Only DB access is fine for analysis)
            stats = await self._get_segment_stats(session)
            
            # 2. Reason about the state of the market
            prompt = f"Analyze these customer segment distributions: {stats}. Are we healthy? Trends?"
            try:
                res = await self.router.complete(
                    task_type='strategy_generation',
                    system_prompt="You are a Market Analyst.",
                    user_prompt=prompt,
                    merchant_id=self.merchant_id
                )
                reasoning = res['content']
            except:
                reasoning = "Automated segment tracking."

            # 3. Push to Internal API (Write via API)
            await self._authenticate()
            if self._api_token:
                import aiohttp
                headers = {"Authorization": f"Bearer {self._api_token}"}
                async with aiohttp.ClientSession() as http:
                    await http.post(
                        "http://localhost:8000/internal/agents/matchmaker/segments",
                        json={"segment_counts": stats, "reasoning": reasoning},
                        headers=headers
                    )
            
            return stats
