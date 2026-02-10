"""
Products API Router.

Provides endpoints for querying products with dead stock filtering.
"""

from typing import List, Optional
from decimal import Decimal

from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Product
from app.auth_middleware import get_current_tenant
from app.limiter import limiter
from fastapi import Request

router = APIRouter()


class ProductResponse(BaseModel):
    """Response model for products."""
    id: str
    shopify_product_id: int
    title: str
    handle: str
    product_type: Optional[str]
    vendor: Optional[str]
    status: str
    total_inventory: int
    variant_count: int
    velocity_score: Optional[float]
    is_dead_stock: bool
    dead_stock_severity: Optional[str]
    days_since_last_sale: Optional[int]
    units_sold_30d: int
    units_sold_90d: int
    revenue_30d: float
    inventory_value: float = 0.0

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    """Response model for product list."""
    products: List[ProductResponse]
    total: int
    dead_stock_count: int


@router.get("", response_model=ProductListResponse)
@limiter.limit("60/minute")
async def list_products(
    request: Request,
    merchant_id: str = Depends(get_current_tenant),
    is_dead_stock: Optional[bool] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """
    List products with high-performance optimized queries.
    """
    # 1. Main Data Query
    query = select(Product).where(Product.merchant_id == merchant_id)
    
    if is_dead_stock is not None:
        query = query.where(Product.is_dead_stock == is_dead_stock)
    
    if severity:
        query = query.where(Product.dead_stock_severity == severity)
    
    # Eager load variants only if needed for list display, usually count is enough
    # If list relies on variant fields, add options(selectinload(Product.variants))
    query = query.order_by(desc(Product.velocity_score)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    products = result.scalars().all()
    
    # 2. Optimized COUNT Queries (Database-side)
    # Get total count
    total_query = select(func.count(Product.id)).where(Product.merchant_id == merchant_id)
    total = (await db.execute(total_query)).scalar() or 0
    
    # Get dead stock count
    dead_query = select(func.count(Product.id)).where(
        Product.merchant_id == merchant_id,
        Product.is_dead_stock == True
    )
    dead_count = (await db.execute(dead_query)).scalar() or 0
    
    return ProductListResponse(
        products=[ProductResponse.model_validate(p) for p in products],
        total=total,
        dead_stock_count=dead_count,
    )


@router.get("/dead-stock-summary")
async def get_dead_stock_summary(
    merchant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Get summary of dead stock by severity.
    Optimized with eager loading.
    """
    from sqlalchemy.orm import selectinload
    
    result = await db.execute(
        select(Product)
        .where(
            Product.merchant_id == merchant_id,
            Product.is_dead_stock == True
        )
        .options(selectinload(Product.variants))  # ✅ Fix N+1 Query
    )
    dead_products = result.scalars().all()
    
    summary = {
        "total_dead_stock": len(dead_products),
        "by_severity": {
            "critical": 0,
            "high": 0,
            "moderate": 0,
            "low": 0,
        },
        "total_units_locked": 0,
        "estimated_value_locked": 0,
        "estimated_holding_cost": 0,
    }
    
    for product in dead_products:
        if product.dead_stock_severity:
            summary["by_severity"][product.dead_stock_severity] += 1
        summary["total_units_locked"] += product.total_inventory
        
        # Estimate value locked (rough calculation)
        if product.variants:
            avg_price = sum(v.price for v in product.variants) / len(product.variants)
            summary["estimated_value_locked"] += float(avg_price) * product.total_inventory
        
        # Estimate holding cost
        if product.holding_cost_per_day:
            days = product.days_since_last_sale or 90
            summary["estimated_holding_cost"] += float(product.holding_cost_per_day) * days
    
    return summary
