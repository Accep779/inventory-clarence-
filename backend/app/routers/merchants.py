"""
Merchants API Router.

Provides endpoints for merchant management.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Merchant
from app.auth_middleware import get_current_tenant

router = APIRouter()


class MerchantResponse(BaseModel):
    """Response model for merchant."""
    id: str
    shopify_domain: str
    store_name: str
    email: str
    plan: str
    is_active: bool
    max_auto_discount: float
    max_auto_ad_spend: float

    class Config:
        from_attributes = True


class MerchantSettingsUpdate(BaseModel):
    """Request model for updating merchant settings."""
    max_auto_discount: Optional[float] = None
    max_auto_ad_spend: Optional[float] = None


@router.get("/me", response_model=MerchantResponse)
async def get_merchant(
    merchant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get current merchant details."""
    result = await db.execute(
        select(Merchant).where(Merchant.id == merchant_id)
    )
    merchant = result.scalar_one_or_none()
    
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    
    return MerchantResponse.model_validate(merchant)


@router.patch("/me/settings")
async def update_merchant_settings(
    settings: MerchantSettingsUpdate,
    merchant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Update merchant agent settings.
    
    These settings control agent autonomy levels:
    - max_auto_discount: Maximum discount agent can apply without approval
    - max_auto_ad_spend: Maximum ad spend agent can approve automatically
    """
    result = await db.execute(
        select(Merchant).where(Merchant.id == merchant_id)
    )
    merchant = result.scalar_one_or_none()
    
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    
    if settings.max_auto_discount is not None:
        if settings.max_auto_discount < 0 or settings.max_auto_discount > 1:
            raise HTTPException(status_code=400, detail="max_auto_discount must be between 0 and 1")
        merchant.max_auto_discount = settings.max_auto_discount
    
    if settings.max_auto_ad_spend is not None:
        if settings.max_auto_ad_spend < 0:
            raise HTTPException(status_code=400, detail="max_auto_ad_spend must be positive")
        merchant.max_auto_ad_spend = settings.max_auto_ad_spend
    
    await db.commit()
    
    return {"status": "updated", "merchant_id": merchant_id}


@router.get("/me/stats")
async def get_merchant_stats(
    merchant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Get high-level stats for merchant dashboard.
    """
    result = await db.execute(
        select(Merchant).where(Merchant.id == merchant_id)
    )
    merchant = result.scalar_one_or_none()
    
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    
    # Count products
    from app.models import Product, Customer, InboxItem, Campaign
    
    products_result = await db.execute(
        select(Product).where(Product.merchant_id == merchant_id)
    )
    products = products_result.scalars().all()
    
    customers_result = await db.execute(
        select(Customer).where(Customer.merchant_id == merchant_id)
    )
    customers = customers_result.scalars().all()
    
    pending_result = await db.execute(
        select(InboxItem).where(
            InboxItem.merchant_id == merchant_id,
            InboxItem.status == "pending"
        )
    )
    pending_items = pending_result.scalars().all()
    
    campaigns_result = await db.execute(
        select(Campaign).where(
            Campaign.merchant_id == merchant_id,
            Campaign.status == "active"
        )
    )
    active_campaigns = campaigns_result.scalars().all()
    
    dead_stock = [p for p in products if p.is_dead_stock]
    
    return {
        "total_products": len(products),
        "total_customers": len(customers),
        "dead_stock_count": len(dead_stock),
        "pending_proposals": len(pending_items),
        "active_campaigns": len(active_campaigns),
        "critical_dead_stock": len([p for p in dead_stock if p.dead_stock_severity == "critical"]),
    }


@router.get("/me/dashboard/summary")
async def get_dashboard_summary(
    merchant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Consolidated dashboard summary for the Overview page.
    """
    try:
        result = await db.execute(
            select(Merchant).where(Merchant.id == merchant_id)
        )
        merchant = result.scalar_one_or_none()
        
        if not merchant:
            raise HTTPException(status_code=404, detail="Merchant not found")
        
        from app.models import Product, InboxItem, Ledger
        from sqlalchemy import func
        
        # Stagnant Inventory Info
        products_res = await db.execute(
            select(Product).where(Product.merchant_id == merchant_id, Product.is_dead_stock == True)
        )
        stagnant_items = products_res.scalars().all()
        
        total_stagnant_value = sum([float(p.cost_per_unit or 0) * p.total_inventory for p in stagnant_items])
        
        # Recovered Revenue & ROI
        from app.services.attribution import AttributionService
        attr_svc = AttributionService(merchant_id)
        roi_stats = await attr_svc.get_roi_stats()
        
        # Pending Proposals
        pending_res = await db.execute(
            select(func.count(InboxItem.id)).where(
                InboxItem.merchant_id == merchant_id,
                InboxItem.status == "pending"
            )
        )
        pending_count = pending_res.scalar() or 0
        
        return {
            "merchant_name": merchant.store_name,
            "metrics": {
                "recovered_revenue": roi_stats["total_recovered_revenue"],
                "roi_multiplier": roi_stats["roi_multiplier"],
                "stagnant_inventory_count": len(stagnant_items),
                "stagnant_inventory_value": total_stagnant_value,
                "pending_proposals": pending_count,
            },
            "daily_summary": f"Today, Cephly is monitoring {len(stagnant_items)} stagnant items and has {pending_count} actions awaiting your review."
        }
    except Exception as e:
        import traceback
        print(f"ERROR in dashboard_summary: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
