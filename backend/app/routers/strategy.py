"""
Strategy API Router.

Provides endpoints for triggering and managing clearance strategies.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Product, InboxItem
from app.agents.strategy import StrategyAgent
from app.auth_middleware import get_current_tenant
from app.limiter import limiter

router = APIRouter()


class StrategyPlanRequest(BaseModel):
    """Request to plan clearance for a product."""
    product_id: str


class BulkStrategyRequest(BaseModel):
    """Request to plan clearance for all dead stock."""
    severity_filter: Optional[list] = ["critical", "high"]


@router.post("/plan")
@limiter.limit("10/minute")
async def plan_clearance(
    request: Request,
    body: StrategyPlanRequest,
    merchant_id: str = Depends(get_current_tenant),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger Strategy Agent to create clearance plan for a product.
    
    This creates an inbox proposal for the merchant.
    """
    # Verify product exists and belongs to merchant
    result = await db.execute(
        select(Product).where(
            Product.id == body.product_id,
            Product.merchant_id == merchant_id,
        )
    )
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if not product.is_dead_stock:
        raise HTTPException(
            status_code=400, 
            detail="Product is not classified as dead stock. Run Observer Agent first."
        )
    
    # Run strategy agent
    try:
        agent = StrategyAgent(merchant_id)
        result = await agent.plan_clearance(body.product_id)
        
        return {
            "status": "success",
            "message": f"Clearance plan created for {product.title}",
            "strategy": result["strategy"],
            "requires_approval": result["requires_approval"],
            "projections": result["projections"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plan-all")
async def plan_clearance_for_all(
    request: BulkStrategyRequest,
    merchant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger Strategy Agent to create plans for all dead stock products.
    
    Filters by severity (default: critical and high).
    """
    # Get all matching dead stock products
    result = await db.execute(
        select(Product).where(
            Product.merchant_id == merchant_id,
            Product.is_dead_stock == True,
            Product.dead_stock_severity.in_(request.severity_filter),
        )
    )
    products = result.scalars().all()
    
    if not products:
        return {
            "status": "no_products",
            "message": "No dead stock products found matching criteria",
        }
    
    # Process each product
    results = []
    agent = StrategyAgent(merchant_id)
    
    for product in products:
        try:
            plan = await agent.plan_clearance(product.id)
            results.append({
                "product_id": product.id,
                "title": product.title,
                "status": "success",
                "strategy": plan["strategy"],
            })
        except Exception as e:
            results.append({
                "product_id": product.id,
                "title": product.title,
                "status": "error",
                "error": str(e),
            })
    
    success_count = len([r for r in results if r["status"] == "success"])
    
    return {
        "status": "completed",
        "total_products": len(products),
        "success_count": success_count,
        "error_count": len(products) - success_count,
        "results": results,
    }


@router.get("/strategies")
async def list_strategies(merchant_id: str = Depends(get_current_tenant)):
    """
    List all available clearance strategies.
    Requires authentication.
    """
    from app.agents.strategy import CLEARANCE_STRATEGIES
    
    return {
        "strategies": [
            {
                "name": key,
                "display_name": value["name"],
                "description": value["description"],
                "best_for": value["best_for"],
                "duration_days": value["duration_days"],
            }
            for key, value in CLEARANCE_STRATEGIES.items()
        ]
    }


@router.get("/proposals")
async def list_strategy_proposals(
    merchant_id: str = Depends(get_current_tenant),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    List all strategy proposals for a merchant.
    """
    query = select(InboxItem).where(
        InboxItem.merchant_id == merchant_id,
        InboxItem.type == "clearance_proposal",
    )
    
    if status:
        query = query.where(InboxItem.status == status)
    
    result = await db.execute(query.order_by(InboxItem.created_at.desc()))
    items = result.scalars().all()
    
    return {
        "proposals": [
            {
                "id": item.id,
                "status": item.status,
                "confidence": float(item.confidence or 0),
                "product_title": item.proposal_data.get("product_title"),
                "strategy": item.proposal_data.get("strategy_name"),
                "pricing": item.proposal_data.get("pricing"),
                "projections": item.proposal_data.get("projections"),
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ],
        "total": len(items),
    }
