"""
Router Dependencies
====================

Shared FastAPI dependencies for router authentication and authorization.
"""

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_middleware import get_current_tenant
from app.database import get_db
from app.models import Merchant


async def require_merchant(
    merchant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
) -> Merchant:
    """
    Dependency that validates JWT and returns the full Merchant object.
    
    Use when you need access to the full merchant record, not just the ID.
    
    Returns:
        Merchant: The authenticated merchant's database record.
        
    Raises:
        HTTPException(401): If JWT is invalid.
        HTTPException(404): If merchant not found in database.
    """
    result = await db.execute(
        select(Merchant).where(Merchant.id == merchant_id)
    )
    merchant = result.scalar_one_or_none()
    
    if not merchant:
        raise HTTPException(status_code=404, detail="Merchant not found")
    
    if not merchant.is_active:
        raise HTTPException(status_code=403, detail="Merchant account is inactive")
    
    return merchant


async def get_session():
    """
    Async database session dependency.
    
    Alias for get_db for compatibility.
    """
    from app.database import async_session_maker
    async with async_session_maker() as session:
        yield session
