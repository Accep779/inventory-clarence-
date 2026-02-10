# app/routers/dna.py
"""
Store DNA API Router
====================
Endpoints for managing Store DNA, including:
- Brand guide upload
- Floor pricing CSV upload
- URL scraping for brand intelligence
- Agent context retrieval
"""

import logging
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Body, Depends
from pydantic import BaseModel

from app.services.dna import DNAService
from app.services.floor_pricing import FloorPricingService
from app.auth_middleware import get_current_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Store DNA"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ScrapeRequest(BaseModel):
    store_url: str


class IdentityRequest(BaseModel):
    description: str


class BrandGuideRequest(BaseModel):
    markdown_content: str


class DNASummary(BaseModel):
    brand_tone: Optional[str] = None
    industry_type: Optional[str] = None
    brand_values: Optional[list] = None
    has_brand_guide: bool = False
    has_scraped_data: bool = False
    identity_description: Optional[str] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/brand-guide")
async def upload_brand_guide(
    merchant_id: str = Depends(get_current_tenant),
    file: Optional[UploadFile] = File(None),
    body: Optional[BrandGuideRequest] = None
):
    """
    Upload markdown brand guide.
    Can accept either a .md file upload or JSON body with markdown_content.
    """
    try:
        markdown_content = None
        
        if file:
            if not file.filename.endswith('.md'):
                raise HTTPException(status_code=400, detail="File must be a .md markdown file")
            content = await file.read()
            markdown_content = content.decode('utf-8')
        elif body:
            markdown_content = body.markdown_content
        else:
            raise HTTPException(status_code=400, detail="No brand guide content provided")
        
        dna_service = DNAService(merchant_id)
        result = await dna_service.process_brand_guide(markdown_content)
        
        if result.get("status") == "FAILED":
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Brand guide upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/floor-pricing")
async def upload_floor_pricing(
    merchant_id: str = Depends(get_current_tenant),
    file: UploadFile = File(...)
):
    """
    Upload floor pricing CSV.
    
    Expected columns:
    - sku OR shopify_product_id (at least one required)
    - cost_price (required)
    - min_margin_pct (optional)
    - floor_price (optional)
    - liquidation_mode (optional, true/false)
    - notes (optional)
    """
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a .csv file")
        
        content = await file.read()
        
        service = FloorPricingService(merchant_id)
        result = await service.parse_csv(content)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Floor pricing upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/floor-pricing")
async def get_floor_pricing(merchant_id: str = Depends(get_current_tenant)):
    """Get all floor pricing records for a merchant."""
    try:
        service = FloorPricingService(merchant_id)
        records = await service.get_all_floor_pricing()
        return {"records": records, "count": len(records)}
    except Exception as e:
        logger.error(f"Get floor pricing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scrape")
async def trigger_store_scrape(
    merchant_id: str = Depends(get_current_tenant),
    body: ScrapeRequest = Body(...)
):
    """
    Trigger URL scraping for DNA enrichment.
    Scrapes homepage and about page, extracts brand signals.
    """
    try:
        dna_service = DNAService(merchant_id)
        result = await dna_service.enrich_from_scrape(body.store_url)
        
        if result.get("status") == "FAILED":
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Store scrape error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/identity")
async def save_identity_description(
    merchant_id: str = Depends(get_current_tenant),
    body: IdentityRequest = Body(...)
):
    """Save the merchant's identity description."""
    try:
        dna_service = DNAService(merchant_id)
        result = await dna_service.save_identity_description(body.description)
        return result
    except Exception as e:
        logger.error(f"Save identity error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/context")
async def get_agent_context(merchant_id: str = Depends(get_current_tenant)):
    """
    Get complete agent context string.
    Returns the full DNA context formatted for injection into agent prompts.
    """
    try:
        dna_service = DNAService(merchant_id)
        context = await dna_service.get_agent_context()
        return {"context": context}
    except Exception as e:
        logger.error(f"Get context error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_dna_summary(merchant_id: str = Depends(get_current_tenant)):
    """Get a summary of the merchant's Store DNA."""
    try:
        dna = await DNAService.get_merchant_dna(merchant_id)
        
        if not dna:
            return DNASummary()
        
        return DNASummary(
            brand_tone=dna.brand_tone,
            industry_type=dna.industry_type,
            brand_values=dna.brand_values,
            has_brand_guide=bool(dna.brand_guide_raw),
            has_scraped_data=bool(dna.scraped_homepage_meta),
            identity_description=dna.identity_description
        )
    except Exception as e:
        logger.error(f"Get DNA summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/floor-pricing/template")
async def get_floor_pricing_template():
    """Returns a sample CSV template for floor pricing upload."""
    return {
        "template": "sku,cost_price,min_margin_pct,floor_price,liquidation_mode,notes\nSKU-001,25.00,20,,false,Regular product\nSKU-002,15.00,15,18.00,true,Clearance item",
        "columns": [
            {"name": "sku", "description": "Product SKU (or use shopify_product_id)", "required": True},
            {"name": "cost_price", "description": "What you paid for the product", "required": True},
            {"name": "min_margin_pct", "description": "Minimum margin % to maintain (e.g., 20 = 20%)", "required": False},
            {"name": "floor_price", "description": "Absolute minimum sale price", "required": False},
            {"name": "liquidation_mode", "description": "Allow at-cost sales? (true/false)", "required": False},
            {"name": "notes", "description": "Any special instructions", "required": False}
        ]
    }
