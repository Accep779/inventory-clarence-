# app/services/floor_pricing.py
"""
Floor Pricing Service
=====================
Manages pricing constraints for clearance strategies.
Prevents agents from suggesting discounts that violate margin requirements.
"""

import csv
import io
import logging
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.database import async_session_maker
from app.models import FloorPricing, Product, ProductVariant

logger = logging.getLogger(__name__)


@dataclass
class MarginResult:
    """Result of a margin compliance check."""
    is_compliant: bool
    floor_price: Optional[Decimal]
    cost_price: Optional[Decimal]
    min_margin_pct: Optional[Decimal]
    liquidation_allowed: bool
    message: str


class FloorPricingService:
    """
    Manages pricing constraints for clearance strategies.
    Ensures agents respect merchant's margin requirements.
    
    Production Features:
    - Staleness detection (warns if data > 30 days old)
    - Validation (floor price < original product price)
    """
    
    STALENESS_THRESHOLD_DAYS = 30  # Warn if floor pricing older than this
    
    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
    
    async def check_data_quality(self) -> Dict[str, Any]:
        """
        Check floor pricing data quality.
        
        Returns:
            Dict with staleness info, validation issues, etc.
        """
        async with async_session_maker() as session:
            result = await session.execute(
                select(FloorPricing).where(FloorPricing.merchant_id == self.merchant_id)
            )
            records = result.scalars().all()
            
            if not records:
                return {
                    "status": "NO_DATA",
                    "message": "No floor pricing data uploaded",
                    "stale_count": 0,
                    "validation_issues": []
                }
            
            now = datetime.utcnow()
            threshold = now - timedelta(days=self.STALENESS_THRESHOLD_DAYS)
            
            stale_records = []
            validation_issues = []
            
            for record in records:
                # Staleness check
                if record.updated_at < threshold:
                    days_old = (now - record.updated_at).days
                    stale_records.append({
                        "sku": record.sku,
                        "product_id": record.product_id,
                        "days_old": days_old
                    })
                
                # Validation: floor price should be reasonable
                if record.floor_price and record.cost_price:
                    if record.floor_price < record.cost_price and not record.liquidation_mode:
                        validation_issues.append({
                            "sku": record.sku,
                            "issue": "FLOOR_BELOW_COST",
                            "floor": float(record.floor_price),
                            "cost": float(record.cost_price)
                        })
            
            # Check floor vs actual product price
            product_issues = await self._check_floor_vs_product_price(session, records)
            validation_issues.extend(product_issues)
            
            is_stale = len(stale_records) > 0
            has_issues = len(validation_issues) > 0
            
            return {
                "status": "WARNING" if (is_stale or has_issues) else "HEALTHY",
                "message": self._build_quality_message(stale_records, validation_issues),
                "stale_count": len(stale_records),
                "stale_records": stale_records[:5],  # Limit to first 5
                "validation_issues": validation_issues[:5],
                "total_records": len(records),
                "newest_update": max(r.updated_at for r in records).isoformat() if records else None
            }
    
    async def _check_floor_vs_product_price(
        self, 
        session, 
        floor_records: List[FloorPricing]
    ) -> List[Dict[str, Any]]:
        """Check if any floor prices exceed original product prices."""
        issues = []
        
        for record in floor_records:
            if not record.product_id or not record.floor_price:
                continue
            
            # Get product's current price
            product_result = await session.execute(
                select(Product).where(Product.id == record.product_id)
                .options(selectinload(Product.variants))
            )
            product = product_result.scalar_one_or_none()
            
            if not product or not product.variants:
                continue
            
            # Get lowest variant price
            min_price = min(v.price for v in product.variants)
            
            if record.floor_price > min_price:
                issues.append({
                    "sku": record.sku,
                    "product_title": product.title[:50],
                    "issue": "FLOOR_EXCEEDS_PRICE",
                    "floor": float(record.floor_price),
                    "current_price": float(min_price),
                    "message": f"Floor ${record.floor_price} > current price ${min_price}"
                })
        
        return issues
    
    def _build_quality_message(
        self, 
        stale_records: List, 
        validation_issues: List
    ) -> str:
        """Build human-readable quality summary."""
        parts = []
        
        if stale_records:
            parts.append(f"{len(stale_records)} records older than {self.STALENESS_THRESHOLD_DAYS} days")
        
        if validation_issues:
            parts.append(f"{len(validation_issues)} validation issues")
        
        if not parts:
            return "Floor pricing data is healthy"
        
        return "Issues found: " + ", ".join(parts)

    async def parse_csv(self, file_content: bytes) -> Dict[str, Any]:
        """
        Parses uploaded CSV, validates, and creates FloorPricing records.
        
        Expected CSV columns:
        - sku OR shopify_product_id (required - at least one)
        - cost_price (required)
        - min_margin_pct (optional)
        - floor_price (optional)
        - liquidation_mode (optional, defaults to false)
        - notes (optional)
        """
        logger.info(f"📊 Parsing floor pricing CSV for merchant {self.merchant_id}")
        
        try:
            # Decode and parse CSV
            content = file_content.decode('utf-8-sig')  # Handle BOM
            reader = csv.DictReader(io.StringIO(content))
            
            records_created = 0
            records_updated = 0
            errors = []
            
            async with async_session_maker() as session:
                # Clear existing floor pricing for this merchant (full replace)
                await session.execute(
                    delete(FloorPricing).where(FloorPricing.merchant_id == self.merchant_id)
                )
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                    try:
                        # Normalize keys (lowercase, strip whitespace)
                        row = {k.lower().strip(): v.strip() for k, v in row.items() if k}
                        
                        # Validate required fields
                        sku = row.get('sku', '').strip() or None
                        shopify_id_str = row.get('shopify_product_id', '').strip()
                        shopify_product_id = int(shopify_id_str) if shopify_id_str else None
                        
                        if not sku and not shopify_product_id:
                            errors.append(f"Row {row_num}: Must have either 'sku' or 'shopify_product_id'")
                            continue
                        
                        cost_str = row.get('cost_price', '').strip()
                        if not cost_str:
                            errors.append(f"Row {row_num}: 'cost_price' is required")
                            continue
                        
                        try:
                            cost_price = Decimal(cost_str)
                        except InvalidOperation:
                            errors.append(f"Row {row_num}: Invalid cost_price '{cost_str}'")
                            continue
                        
                        # Optional fields
                        min_margin_str = row.get('min_margin_pct', '').strip()
                        min_margin_pct = Decimal(min_margin_str) if min_margin_str else None
                        
                        floor_str = row.get('floor_price', '').strip()
                        floor_price = Decimal(floor_str) if floor_str else None
                        
                        liq_str = row.get('liquidation_mode', '').strip().lower()
                        liquidation_mode = liq_str in ('true', '1', 'yes', 'y')
                        
                        notes = row.get('notes', '').strip() or None
                        
                        # Try to link to actual product
                        product_id = await self._find_product_id(session, sku, shopify_product_id)
                        
                        # Create record
                        floor_record = FloorPricing(
                            merchant_id=self.merchant_id,
                            sku=sku,
                            shopify_product_id=shopify_product_id,
                            product_id=product_id,
                            cost_price=cost_price,
                            min_margin_pct=min_margin_pct,
                            floor_price=floor_price,
                            liquidation_mode=liquidation_mode,
                            notes=notes,
                            source="csv_upload"
                        )
                        session.add(floor_record)
                        records_created += 1
                        
                    except Exception as e:
                        errors.append(f"Row {row_num}: {str(e)}")
                
                await session.commit()
            
            logger.info(f"✅ Floor pricing import complete: {records_created} created, {len(errors)} errors")
            
            return {
                "status": "SUCCESS" if not errors else "PARTIAL",
                "records_created": records_created,
                "errors": errors[:10],  # Limit to first 10 errors
                "total_errors": len(errors)
            }
            
        except Exception as e:
            logger.error(f"Floor pricing CSV parse error: {e}")
            return {
                "status": "FAILED",
                "error": str(e),
                "records_created": 0
            }

    async def _find_product_id(self, session, sku: Optional[str], shopify_product_id: Optional[int]) -> Optional[str]:
        """Attempt to find the internal product_id from SKU or Shopify ID."""
        if shopify_product_id:
            result = await session.execute(
                select(Product.id).where(
                    Product.merchant_id == self.merchant_id,
                    Product.shopify_product_id == shopify_product_id
                )
            )
            product = result.scalar_one_or_none()
            if product:
                return product
        
        if sku:
            # Check variants for SKU match
            result = await session.execute(
                select(ProductVariant.product_id)
                .join(Product)
                .where(
                    Product.merchant_id == self.merchant_id,
                    ProductVariant.sku == sku
                )
            )
            variant = result.scalar_one_or_none()
            if variant:
                return variant
        
        return None

    async def check_margin_compliance(
        self, 
        product_id: str, 
        proposed_price: Decimal
    ) -> MarginResult:
        """
        Check if a proposed price meets margin requirements.
        Returns compliance status and details.
        """
        async with async_session_maker() as session:
            # Find floor pricing record
            result = await session.execute(
                select(FloorPricing).where(
                    FloorPricing.merchant_id == self.merchant_id,
                    FloorPricing.product_id == product_id
                )
            )
            floor_record = result.scalar_one_or_none()
            
            if not floor_record:
                # No constraints defined = compliant
                return MarginResult(
                    is_compliant=True,
                    floor_price=None,
                    cost_price=None,
                    min_margin_pct=None,
                    liquidation_allowed=False,
                    message="No floor pricing constraints defined"
                )
            
            cost = floor_record.cost_price
            
            # Check absolute floor
            if floor_record.floor_price and proposed_price < floor_record.floor_price:
                return MarginResult(
                    is_compliant=False,
                    floor_price=floor_record.floor_price,
                    cost_price=cost,
                    min_margin_pct=floor_record.min_margin_pct,
                    liquidation_allowed=floor_record.liquidation_mode,
                    message=f"Price ${proposed_price} is below floor price ${floor_record.floor_price}"
                )
            
            # Check margin percentage
            if floor_record.min_margin_pct and cost > 0:
                margin = ((proposed_price - cost) / proposed_price) * 100
                if margin < floor_record.min_margin_pct:
                    if floor_record.liquidation_mode and proposed_price >= cost:
                        return MarginResult(
                            is_compliant=True,
                            floor_price=floor_record.floor_price,
                            cost_price=cost,
                            min_margin_pct=floor_record.min_margin_pct,
                            liquidation_allowed=True,
                            message=f"Liquidation mode: accepting {margin:.1f}% margin (min was {floor_record.min_margin_pct}%)"
                        )
                    return MarginResult(
                        is_compliant=False,
                        floor_price=floor_record.floor_price,
                        cost_price=cost,
                        min_margin_pct=floor_record.min_margin_pct,
                        liquidation_allowed=floor_record.liquidation_mode,
                        message=f"Margin {margin:.1f}% is below minimum {floor_record.min_margin_pct}%"
                    )
            
            # Check if selling below cost
            if proposed_price < cost and not floor_record.liquidation_mode:
                return MarginResult(
                    is_compliant=False,
                    floor_price=floor_record.floor_price,
                    cost_price=cost,
                    min_margin_pct=floor_record.min_margin_pct,
                    liquidation_allowed=False,
                    message=f"Price ${proposed_price} is below cost ${cost}"
                )
            
            return MarginResult(
                is_compliant=True,
                floor_price=floor_record.floor_price,
                cost_price=cost,
                min_margin_pct=floor_record.min_margin_pct,
                liquidation_allowed=floor_record.liquidation_mode,
                message="Price meets margin requirements"
            )

    async def get_floor_price(self, product_id: str) -> Optional[Decimal]:
        """
        Get the effective floor price for a product.
        Calculates from cost + margin if no explicit floor is set.
        """
        async with async_session_maker() as session:
            result = await session.execute(
                select(FloorPricing).where(
                    FloorPricing.merchant_id == self.merchant_id,
                    FloorPricing.product_id == product_id
                )
            )
            floor_record = result.scalar_one_or_none()
            
            if not floor_record:
                return None
            
            # Explicit floor takes priority
            if floor_record.floor_price:
                return floor_record.floor_price
            
            # Calculate from cost + margin
            if floor_record.min_margin_pct and floor_record.cost_price:
                # floor = cost / (1 - margin_pct/100)
                margin_decimal = floor_record.min_margin_pct / Decimal("100")
                if margin_decimal < 1:
                    return floor_record.cost_price / (Decimal("1") - margin_decimal)
            
            # If liquidation mode, floor is cost
            if floor_record.liquidation_mode:
                return floor_record.cost_price
            
            return None

    async def can_liquidate(self, product_id: str) -> bool:
        """Check if product is flagged for at-cost liquidation."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(FloorPricing.liquidation_mode).where(
                    FloorPricing.merchant_id == self.merchant_id,
                    FloorPricing.product_id == product_id
                )
            )
            mode = result.scalar_one_or_none()
            return bool(mode)

    async def get_floor_record(self, product_id: str, session=None) -> Optional[FloorPricing]:
        """Get the full floor pricing record for detailed validation."""
        if session:
            result = await session.execute(
                select(FloorPricing).where(
                    FloorPricing.merchant_id == self.merchant_id,
                    FloorPricing.product_id == product_id
                )
            )
            return result.scalar_one_or_none()
            
        async with async_session_maker() as session:
            result = await session.execute(
                select(FloorPricing).where(
                    FloorPricing.merchant_id == self.merchant_id,
                    FloorPricing.product_id == product_id
                )
            )
            return result.scalar_one_or_none()

    async def get_all_floor_pricing(self) -> List[Dict[str, Any]]:
        """Get all floor pricing records for this merchant."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(FloorPricing).where(FloorPricing.merchant_id == self.merchant_id)
            )
            records = result.scalars().all()
            
            return [
                {
                    "id": r.id,
                    "sku": r.sku,
                    "shopify_product_id": r.shopify_product_id,
                    "cost_price": float(r.cost_price),
                    "min_margin_pct": float(r.min_margin_pct) if r.min_margin_pct else None,
                    "floor_price": float(r.floor_price) if r.floor_price else None,
                    "liquidation_mode": r.liquidation_mode,
                    "notes": r.notes
                }
                for r in records
            ]
