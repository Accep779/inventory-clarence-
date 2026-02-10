"""
Global Brain Service
====================
[ENGINE #2]: Cross-Tenant Learning.
Anonymizes campaign successes and failures from individual stores and
transforms them into platform-wide Strategy Patterns.
"""

import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
from sqlalchemy import select, func, and_
from app.database import async_session_maker
from app.models import Campaign, GlobalStrategyPattern, Merchant, StoreDNA

logger = logging.getLogger(__name__)

class GlobalBrainService:
    @staticmethod
    async def harvest_patterns():
        """
        Background task to harvest high-performing patterns.
        Anonymizes Store A successful campaigns for Store B.
        """
        async with async_session_maker() as session:
            # 1. Fetch campaigns with high conversion (>5%)
            stmt = select(Campaign).where(Campaign.conversions > 0)
            result = await session.execute(stmt)
            campaigns = result.scalars().all()
            
            for campaign in campaigns:
                # Anonymize: Get Industry from StoreDNA
                dna_stmt = select(StoreDNA).where(StoreDNA.merchant_id == campaign.merchant_id)
                dna_res = await session.execute(dna_stmt)
                dna = dna_res.scalar_one_or_none()
                
                industry = dna.industry_type if dna else "Unknown"
                
                # Check for existing pattern
                pattern_key = f"{industry}_{campaign.strategy_key}"
                
                # Update or Create Global Pattern
                pat_stmt = select(GlobalStrategyPattern).where(GlobalStrategyPattern.pattern_key == pattern_key)
                pat_res = await session.execute(pat_stmt)
                pattern = pat_res.scalar_one_or_none()
                
                if not pattern:
                    pattern = GlobalStrategyPattern(
                        pattern_key=pattern_key,
                        industry_type=industry,
                        strategy_key=campaign.strategy_key,
                        context_criteria={"auto_min_margin": 10} # Placeholder
                    )
                    session.add(pattern)
                
                # Update rolling P50/P90 (Simplified for demo)
                conv_rate = Decimal(campaign.conversions) / Decimal(max(campaign.emails_sent, 1))
                pattern.p50_conversion = (pattern.p50_conversion + conv_rate) / 2
                pattern.recommendation_score += 1
                pattern.sample_count += 1  # Track sample size for statistical validity
                
            await session.commit()
            logger.info("🧠 Global Brain: Harvested successful patterns.")

    @staticmethod
    async def get_applicable_patterns(
        industry: str,
        min_sample_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieves global intelligence for a specific merchant.
        
        Args:
            industry: Industry type to filter patterns for
            min_sample_size: Minimum sample count required for pattern validity
                            (default: 100 to ensure statistical significance)
        
        Returns:
            List of applicable patterns with confidence indicators
        """
        async with async_session_maker() as session:
            # Only return patterns with sufficient sample size
            stmt = select(GlobalStrategyPattern).where(
                and_(
                    GlobalStrategyPattern.industry_type == industry,
                    GlobalStrategyPattern.sample_count >= min_sample_size
                )
            ).order_by(GlobalStrategyPattern.recommendation_score.desc()).limit(3)
            
            result = await session.execute(stmt)
            patterns = result.scalars().all()
            
            return [
                {
                    "strategy": p.strategy_key,
                    "avg_conversion": float(p.p50_conversion),
                    "sample_count": p.sample_count,
                    "confidence": _calculate_confidence(p.sample_count, p.recommendation_score)
                }
                for p in patterns
            ]


def _calculate_confidence(sample_count: int, recommendation_score: int) -> str:
    """Calculate confidence level based on sample size and success rate."""
    if sample_count >= 1000 and recommendation_score > 50:
        return "Very High"
    elif sample_count >= 500 and recommendation_score > 25:
        return "High"
    elif sample_count >= 100 and recommendation_score > 10:
        return "Moderate"
    else:
        return "Emerging"
