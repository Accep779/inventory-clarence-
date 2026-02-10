from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from app.database import get_db
from app.models import Customer, CommercialJourney, TouchLog
from app.auth_middleware import get_current_tenant
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

router = APIRouter()

@router.get("/journeys")
async def get_active_journeys(
    merchant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch all active or recently completed reactivation journeys.
    """
    stmt = (
        select(CommercialJourney, Customer)
        .join(Customer, CommercialJourney.customer_id == Customer.id)
        .where(CommercialJourney.merchant_id == merchant_id)
        .order_by(CommercialJourney.created_at.desc())
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    journeys = []
    for journey, customer in rows:
        journeys.append({
            "id": journey.id,
            "customer_name": f"{customer.first_name} {customer.last_name}",
            "status": journey.status,
            "current_touch": journey.current_touch,
            "last_touch_at": journey.last_touch_at.isoformat() if journey.last_touch_at else None,
            "next_touch_due_at": journey.next_touch_due_at.isoformat() if journey.next_touch_due_at else None,
            "lifetime_value": float(customer.total_spent or 0)
        })
        
    return journeys

@router.get("/stats")
async def get_crm_stats(
    merchant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Aggregate CRM and Retention stats.
    """
    # 1. Reachable Customers
    reachable_stmt = select(func.count(Customer.id)).where(Customer.merchant_id == merchant_id)
    reachable = (await db.execute(reachable_stmt)).scalar() or 0
    
    # 2. At Risk (Simplified logic: no order in 60 days)
    from datetime import datetime, timedelta
    at_risk_date = datetime.utcnow() - timedelta(days=60)
    at_risk_stmt = select(func.count(Customer.id)).where(
        Customer.merchant_id == merchant_id,
        Customer.last_order_date < at_risk_date
    )
    at_risk = (await db.execute(at_risk_stmt)).scalar() or 0
    
    # 3. Recovered (Converted Journeys)
    recovered_stmt = select(func.count(CommercialJourney.id)).where(
        CommercialJourney.merchant_id == merchant_id,
        CommercialJourney.status == 'converted'
    )
    recovered = (await db.execute(recovered_stmt)).scalar() or 0
    
    return {
        "total_reachable": reachable,
        "at_risk_count": at_risk,
        "recovered_count": recovered,
        "neural_lift": "18.4%" # Placeholder
    }
