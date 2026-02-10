# backend/app/routers/seasonal.py
"""
Seasonal API Router
===================

FastAPI endpoints for seasonal risk management.

GET  /api/seasonal/risks    - List seasonal products at risk
POST /api/seasonal/scan     - Trigger manual scan
GET  /api/seasonal/insights - Historical seasonal performance
"""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc

from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.routers.dependencies import get_session, require_merchant
from app.models import Product, InboxItem, Campaign, AgentThought, Merchant
from app.agents.seasonal_transition import SeasonalTransitionAgent
from app.services.seasonal_analyzer import SeasonalAnalyzer, Season

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/seasonal", tags=["Seasonal"])


# ============ SCHEMAS ============

class SeasonalRiskResponse(BaseModel):
    product_id: str
    title: str
    season: str
    days_remaining: int
    risk_level: str
    velocity_decline: float
    confidence: float
    reasoning: str


class SeasonalRisksListResponse(BaseModel):
    risks: List[SeasonalRiskResponse]
    total: int
    by_risk_level: dict


class ScanTriggerRequest(BaseModel):
    async_mode: bool = True


class ScanTriggerResponse(BaseModel):
    status: str
    task_id: Optional[str] = None
    message: str


class SeasonalInsightResponse(BaseModel):
    season: str
    total_campaigns: int
    success_rate: float
    avg_revenue: float
    top_strategy: str


class SeasonalInsightsListResponse(BaseModel):
    insights: List[SeasonalInsightResponse]
    recommendations: List[str]


# ============ ENDPOINTS ============

@router.get("/risks", response_model=SeasonalRisksListResponse)
async def get_seasonal_risks(
    season: Optional[str] = Query(None, description="Filter by season"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    limit: int = Query(50, le=200),
    merchant: Merchant = Depends(require_merchant),
    session: AsyncSession = Depends(get_session)
):
    """
    List all products with seasonal risk assessments.
    
    Returns products identified as seasonal with their risk levels,
    sorted by urgency (critical first).
    """
    analyzer = SeasonalAnalyzer()
    
    # Fetch products with inventory
    query = (
        select(Product)
        .where(Product.merchant_id == merchant.id)
        .where(Product.total_inventory > 0)
        .limit(limit * 2)  # Fetch more to filter
    )
    
    result = await session.execute(query)
    products = result.scalars().all()
    
    risks = []
    for product in products:
        product_dict = {
            'id': product.id,
            'title': product.title,
            'description': product.body_html or '',
            'tags': product.tags.split(',') if product.tags else [],
            'product_type': product.product_type or ''
        }
        
        risk = analyzer.assess_risk(product_dict)
        
        # Skip year-round products
        if risk.detected_season == Season.YEAR_ROUND:
            continue
        
        # Apply filters
        if season and risk.detected_season.value != season:
            continue
        if risk_level and risk.risk_level != risk_level:
            continue
        
        risks.append(SeasonalRiskResponse(
            product_id=product.id,
            title=product.title,
            season=risk.detected_season.value,
            days_remaining=risk.days_until_season_end,
            risk_level=risk.risk_level,
            velocity_decline=risk.predicted_velocity_decline,
            confidence=risk.confidence,
            reasoning=risk.reasoning
        ))
    
    # Sort by risk level priority
    risk_order = {'critical': 0, 'high': 1, 'moderate': 2, 'low': 3}
    risks.sort(key=lambda r: (risk_order.get(r.risk_level, 4), r.days_remaining))
    
    # Risk level breakdown
    by_level = {
        'critical': len([r for r in risks if r.risk_level == 'critical']),
        'high': len([r for r in risks if r.risk_level == 'high']),
        'moderate': len([r for r in risks if r.risk_level == 'moderate']),
        'low': len([r for r in risks if r.risk_level == 'low'])
    }
    
    return SeasonalRisksListResponse(
        risks=risks[:limit],
        total=len(risks),
        by_risk_level=by_level
    )


@router.post("/scan", response_model=ScanTriggerResponse)
async def trigger_seasonal_scan(
    request: ScanTriggerRequest,
    background_tasks: BackgroundTasks,
    merchant: Merchant = Depends(require_merchant)
):
    """
    Trigger a manual seasonal risk scan.
    
    In async mode, returns immediately with a task ID.
    In sync mode, waits for completion (max 30s).
    """
    if request.async_mode:
        # Queue Celery task
        from app.tasks.seasonal_scan import run_seasonal_scan_for_merchant
        task = run_seasonal_scan_for_merchant.delay(merchant.id)
        
        return ScanTriggerResponse(
            status="queued",
            task_id=task.id,
            message="Seasonal scan started. Monitor progress via SSE."
        )
    else:
        # Run synchronously (blocking)
        try:
            agent = SeasonalTransitionAgent(merchant.id)
            risks = await agent.scan_seasonal_risks()
            
            return ScanTriggerResponse(
                status="completed",
                message=f"Found {len(risks)} seasonal products at risk."
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights", response_model=SeasonalInsightsListResponse)
async def get_seasonal_insights(
    merchant: Merchant = Depends(require_merchant),
    session: AsyncSession = Depends(get_session)
):
    """
    Get historical seasonal clearance performance insights.
    
    Analyzes past campaigns to identify what works for each season.
    """
    # Query past seasonal campaigns
    result = await session.execute(
        select(InboxItem)
        .where(InboxItem.merchant_id == merchant.id)
        .where(InboxItem.proposal_type == 'seasonal_clearance')
        .where(InboxItem.status.in_(['executed', 'completed']))
        .order_by(desc(InboxItem.created_at))
        .limit(100)
    )
    proposals = result.scalars().all()
    
    # Aggregate by season
    season_stats = {}
    for proposal in proposals:
        reasoning = proposal.reasoning or {}
        seasonal_risk = reasoning.get('seasonal_risk', {})
        season = seasonal_risk.get('season', 'unknown')
        
        if season not in season_stats:
            season_stats[season] = {
                'campaigns': 0,
                'successes': 0,
                'total_revenue': 0,
                'strategies': {}
            }
        
        stats = season_stats[season]
        stats['campaigns'] += 1
        
        # Determine success (simplified - would check actual metrics)
        projections = reasoning.get('projections', {})
        if projections.get('projected_revenue', 0) > 0:
            stats['successes'] += 1
            stats['total_revenue'] += projections.get('projected_revenue', 0)
        
        # Track strategies
        strategy = proposal.strategy
        stats['strategies'][strategy] = stats['strategies'].get(strategy, 0) + 1
    
    # Build response
    insights = []
    for season, stats in season_stats.items():
        if stats['campaigns'] == 0:
            continue
        
        top_strategy = max(stats['strategies'], key=stats['strategies'].get) if stats['strategies'] else 'N/A'
        
        insights.append(SeasonalInsightResponse(
            season=season,
            total_campaigns=stats['campaigns'],
            success_rate=stats['successes'] / stats['campaigns'] if stats['campaigns'] > 0 else 0,
            avg_revenue=stats['total_revenue'] / stats['campaigns'] if stats['campaigns'] > 0 else 0,
            top_strategy=top_strategy
        ))
    
    # Generate recommendations
    recommendations = []
    for insight in insights:
        if insight.success_rate < 0.5:
            recommendations.append(
                f"⚠️ {insight.season.title()} campaigns have low success rate ({insight.success_rate:.0%}). "
                f"Consider adjusting timing or discounts."
            )
        if insight.success_rate > 0.7:
            recommendations.append(
                f"✅ {insight.season.title()} strategy '{insight.top_strategy}' works well. "
                f"Continue using this approach."
            )
    
    if not recommendations:
        recommendations.append("💡 Start running seasonal campaigns to build insights.")
    
    return SeasonalInsightsListResponse(
        insights=insights,
        recommendations=recommendations
    )


@router.get("/thoughts")
async def get_seasonal_agent_thoughts(
    limit: int = Query(20, le=100),
    merchant: Merchant = Depends(require_merchant),
    session: AsyncSession = Depends(get_session)
):
    """
    Get recent reasoning from the Seasonal Transition Agent.
    
    Useful for debugging and understanding agent decisions.
    """
    result = await session.execute(
        select(AgentThought)
        .where(AgentThought.merchant_id == merchant.id)
        .where(AgentThought.agent_type == 'seasonal')
        .order_by(desc(AgentThought.created_at))
        .limit(limit)
    )
    thoughts = result.scalars().all()
    
    return {
        'thoughts': [
            {
                'id': t.id,
                'type': t.thought_type,
                'summary': t.summary,
                'confidence': t.confidence_score,
                'created_at': t.created_at.isoformat(),
                'details': t.detailed_reasoning
            }
            for t in thoughts
        ]
    }
