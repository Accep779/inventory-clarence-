# app/services/failure_reflector.py
"""
Failure Reflector Service
=========================

WORLD-CLASS PATTERN: Reflection on Failure.

When something fails, don't just log it - ANALYZE WHY it failed
and learn from it for future decisions.

Inspired by: AutoGPT's internal reflection process and Claude's self-correction.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from sqlalchemy import select, desc
from app.database import async_session_maker
from app.models import Campaign, AgentThought
from app.services.thought_logger import ThoughtLogger
from app.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)


class FailureReflector:
    """
    Analyzes failures to extract learnable insights.
    
    This closes the learning loop by:
    1. Detecting failures
    2. Analyzing root causes via LLM
    3. Storing lessons for future agent decisions
    """
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self.router = LLMRouter()
    
    async def reflect_on_campaign_failure(
        self, 
        campaign_id: str,
        failure_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Deep reflection on why a campaign failed.
        
        Returns actionable learnings that can inform future strategy selection.
        """
        async with async_session_maker() as session:
            campaign = await session.get(Campaign, campaign_id)
            if not campaign:
                return {'error': 'Campaign not found'}
            
            # Gather failure context
            emails_sent = campaign.emails_sent or 0
            emails_opened = campaign.emails_opened or 0
            emails_clicked = campaign.emails_clicked or 0
            
            open_rate = emails_opened / emails_sent if emails_sent > 0 else 0
            click_rate = emails_clicked / emails_sent if emails_sent > 0 else 0
            
            # Retrieve related thoughts
            thoughts_result = await session.execute(
                select(AgentThought)
                .where(AgentThought.merchant_id == self.merchant_id)
                .where(AgentThought.detailed_reasoning['campaign_id'].astext == campaign_id)
                .order_by(desc(AgentThought.created_at))
                .limit(5)
            )
            related_thoughts = thoughts_result.scalars().all()
            
            # Build reflection prompt
            prompt = f"""Analyze this failed marketing campaign and identify the root cause.

CAMPAIGN DATA:
- Strategy: {campaign.type}
- Status: {campaign.status}
- Target Segments: {campaign.target_segments}
- Emails Sent: {emails_sent}
- Open Rate: {open_rate:.1%}
- Click Rate: {click_rate:.1%}

AGENT THOUGHTS DURING EXECUTION:
{[{'type': t.thought_type, 'summary': t.summary} for t in related_thoughts]}

ADDITIONAL CONTEXT:
{failure_context or 'None provided'}

ANALYZE:
1. What is the most likely root cause of failure?
2. Was this a strategy problem, audience problem, or timing problem?
3. What should we do differently next time for similar products?

Respond with JSON:
{{
    "root_cause": "brief description",
    "failure_category": "strategy|audience|timing|copy|execution|external",
    "severity": "minor|moderate|critical",
    "lessons": ["lesson 1", "lesson 2"],
    "recommendations": ["recommendation 1", "recommendation 2"],
    "avoid_in_future": ["thing to avoid"]
}}"""

            try:
                response = await self.router.complete(
                    task_type='strategy_generation',
                    system_prompt="You are a marketing failure analyst. Be specific and actionable.",
                    user_prompt=prompt,
                    merchant_id=self.merchant_id
                )
                
                import json
                content = response['content'].strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                
                reflection = json.loads(content)
                
                # Store the reflection as a high-value thought
                await ThoughtLogger.log_thought(
                    merchant_id=self.merchant_id,
                    agent_type="reflector",
                    thought_type="reflection",
                    summary=f"Failure analysis: {reflection.get('root_cause', 'Unknown')}",
                    detailed_reasoning={
                        'campaign_id': campaign_id,
                        'failure_category': reflection.get('failure_category'),
                        'severity': reflection.get('severity'),
                        'lessons': reflection.get('lessons', []),
                        'recommendations': reflection.get('recommendations', []),
                        'avoid_in_future': reflection.get('avoid_in_future', []),
                        'analyzed_at': datetime.utcnow().isoformat()
                    },
                    confidence_score=0.85
                )
                
                logger.info(f"🔍 Reflected on failure for campaign {campaign_id}: {reflection.get('root_cause')}")
                
                return {
                    'success': True,
                    'reflection': reflection
                }
                
            except Exception as e:
                logger.error(f"Reflection failed: {e}")
                return {
                    'success': False,
                    'error': str(e)
                }
    
    async def get_accumulated_lessons(
        self, 
        strategy_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve accumulated lessons from past failures.
        
        This enables agents to learn from collective experience.
        """
        async with async_session_maker() as session:
            query = (
                select(AgentThought)
                .where(AgentThought.merchant_id == self.merchant_id)
                .where(AgentThought.agent_type == "reflector")
                .where(AgentThought.thought_type == "reflection")
                .order_by(desc(AgentThought.created_at))
                .limit(limit)
            )
            
            result = await session.execute(query)
            reflections = result.scalars().all()
            
            lessons = []
            for r in reflections:
                reasoning = r.detailed_reasoning or {}
                
                # Filter by strategy if specified
                if strategy_type:
                    # Would need campaign lookup to filter by strategy
                    pass
                
                lessons.extend(reasoning.get('lessons', []))
            
            # Deduplicate lessons
            unique_lessons = list(set(lessons))
            
            return unique_lessons[:limit]
