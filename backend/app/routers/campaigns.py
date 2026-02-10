
"""
Campaigns API Router.

Provides endpoints for tracking and managing autonomous campaigns.
"""

from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Campaign, Merchant
from app.auth_middleware import get_current_tenant

router = APIRouter(tags=["Campaigns"])


class CampaignResponse(BaseModel):
    """Response model for campaigns."""
    id: str
    name: str
    type: str
    status: str
    emails_sent: int
    emails_opened: int
    emails_clicked: int
    sms_sent: int
    conversions: int
    revenue: float
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class CampaignListResponse(BaseModel):
    """Response model for campaign list."""
    campaigns: List[CampaignResponse]
    total: int
    active_count: int
    total_revenue: float
    total_spend: float  # Estimated/Mocked for now


@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    merchant_id: str = Depends(get_current_tenant),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """
    List campaigns for a merchant.
    """
    query = select(Campaign).where(Campaign.merchant_id == merchant_id)
    
    if status:
        query = query.where(Campaign.status == status)
    
    # Sort by created_at desc
    query = query.order_by(desc(Campaign.created_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    campaigns = result.scalars().all()
    
    # Get aggregates
    # Total Active
    active_res = await db.execute(
        select(func.count(Campaign.id)).where(
            Campaign.merchant_id == merchant_id,
            Campaign.status == "active"
        )
    )
    active_count = active_res.scalar() or 0
    
    # Total Revenue (across all campaigns for this merchant)
    revenue_res = await db.execute(
        select(func.sum(Campaign.revenue)).where(
            Campaign.merchant_id == merchant_id
        )
    )
    total_revenue = float(revenue_res.scalar() or 0)
    
    # Total Spend (Mocked as % of revenue for demo, or 0 if no revenue)
    # In real world, this would sum ad spend + email costs
    total_spend = total_revenue * 0.15 
    
    return CampaignListResponse(
        campaigns=[CampaignResponse.model_validate(c) for c in campaigns],
        total=len(campaigns), # This is page total, ideally request total count separately
        active_count=active_count,
        total_revenue=total_revenue,
        total_spend=total_spend
    )


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    merchant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get specific campaign."""
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.merchant_id == merchant_id
        )
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    return CampaignResponse.model_validate(campaign)


@router.post("/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    merchant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Pause an active campaign."""
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.merchant_id == merchant_id
        )
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.status != "active":
        raise HTTPException(status_code=400, detail=f"Campaign is {campaign.status}, cannot pause")
        
    campaign.status = "paused"
    await db.commit()
    
    return {"status": "paused", "id": campaign_id}


@router.post("/{campaign_id}/resume")
async def resume_campaign(
    campaign_id: str,
    merchant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused campaign."""
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.merchant_id == merchant_id
        )
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    if campaign.status != "paused":
        raise HTTPException(status_code=400, detail=f"Campaign is {campaign.status}, cannot resume")
        
    campaign.status = "active"
    await db.commit()
    
    return {"status": "active", "id": campaign_id}
