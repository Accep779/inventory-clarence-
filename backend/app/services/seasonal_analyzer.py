# backend/app/services/seasonal_analyzer.py
"""
Seasonal Analyzer Service
=========================

Analyzes products for seasonal characteristics and predicts when they
will become dead stock based on season timing and velocity trends.

This is a pure analysis service - no side effects, just data.
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Season(str, Enum):
    SPRING = "spring"
    SUMMER = "summer"
    FALL = "fall"
    WINTER = "winter"
    HOLIDAY = "holiday"
    BACK_TO_SCHOOL = "back_to_school"
    YEAR_ROUND = "year_round"


@dataclass
class SeasonalRisk:
    """Assessment of a product's seasonal risk."""
    product_id: str
    detected_season: Season
    days_until_season_end: int
    risk_level: str  # 'critical', 'high', 'moderate', 'low'
    predicted_velocity_decline: float  # 0-1, percentage decline expected
    confidence: float  # 0-1
    reasoning: str
    max_recommended_discount: float  # [HARDENED] Explicit cap based on window
    clearance_window: str # 'pacing', 'urgency', 'liquidation'


# Season keyword patterns
SEASON_PATTERNS = {
    Season.SPRING: [
        r'\bspring\b', r'\beaster\b', r'\bpastel\b', r'\bfloral\b',
        r'\bgarden\b', r'\bbloom\b', r'\bfresh\b'
    ],
    Season.SUMMER: [
        r'\bsummer\b', r'\bbeach\b', r'\bswim\b', r'\bpool\b',
        r'\bbbq\b', r'\boutdoor\b', r'\bsandal\b', r'\bshort\b',
        r'\btank\b', r'\bsunscreen\b', r'\bsun\b'
    ],
    Season.FALL: [
        r'\bfall\b', r'\bautumn\b', r'\bharvest\b', r'\bpumpkin\b',
        r'\bsweater\b', r'\bcardigan\b', r'\bflannel\b', r'\bcozy\b',
        r'\bthanksgiving\b', r'\bhalloween\b'
    ],
    Season.WINTER: [
        r'\bwinter\b', r'\bsnow\b', r'\bholiday\b', r'\bchristmas\b',
        r'\bcoat\b', r'\bjacket\b', r'\bboot\b', r'\bwarm\b',
        r'\bfleece\b', r'\bparka\b', r'\bbeanie\b', r'\bglove\b'
    ],
    Season.HOLIDAY: [
        r'\bchristmas\b', r'\bxmas\b', r'\bholiday\b', r'\bgift\b',
        r'\bnew\s*year\b', r'\bvalentine\b', r'\bmother\s*day\b',
        r'\bfather\s*day\b', r'\bhanuk\w*\b'
    ],
    Season.BACK_TO_SCHOOL: [
        r'\bschool\b', r'\bbackpack\b', r'\bstudent\b', r'\bcollege\b',
        r'\bsupplies\b', r'\bnotebook\b', r'\bpencil\b'
    ],
}

# Season end dates (month, day) - approximate
SEASON_END_DATES = {
    Season.SPRING: (6, 20),       # June 20
    Season.SUMMER: (9, 22),       # September 22
    Season.FALL: (12, 20),        # December 20
    Season.WINTER: (3, 20),       # March 20
    Season.HOLIDAY: (12, 26),     # December 26
    Season.BACK_TO_SCHOOL: (9, 15),  # September 15
}

# [HARDENED] Explicit Clearance Windows
SEASONAL_WINDOWS = {
    'pacing': {
        'days_min': 30,
        'days_max': 999,
        'max_discount': 0.20,
        'strategy': 'Preserve Margin'
    },
    'urgency': {
        'days_min': 14,
        'days_max': 30,
        'max_discount': 0.40, 
        'strategy': 'Recover Cash'
    },
    'liquidation': {
        'days_min': -999,
        'days_max': 14,
        'max_discount': 0.75,
        'strategy': 'Evacuation'
    }
}


class SeasonalAnalyzer:
    """
    Analyzes products for seasonal patterns and predicts velocity decline.
    """
    
    def __init__(self, current_date: Optional[datetime] = None):
        self.current_date = current_date or datetime.utcnow()
    
    def detect_season(self, product: Dict[str, Any]) -> Tuple[Season, float]:
        """
        Detect the primary season for a product based on its metadata.
        
        Returns (season, confidence_score).
        """
        # Combine all searchable text
        searchable = ' '.join([
            product.get('title', ''),
            product.get('description', ''),
            ' '.join(product.get('tags', [])),
            product.get('product_type', ''),
            product.get('vendor', '')
        ]).lower()
        
        # Score each season
        season_scores = {}
        for season, patterns in SEASON_PATTERNS.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, searchable, re.IGNORECASE))
                score += matches
            if score > 0:
                season_scores[season] = score
        
        if not season_scores:
            return Season.YEAR_ROUND, 0.0
        
        # Get highest scoring season
        best_season = max(season_scores, key=season_scores.get)
        total_score = sum(season_scores.values())
        confidence = season_scores[best_season] / max(total_score, 1)
        
        return best_season, min(0.95, confidence)
    
    def calculate_days_until_season_end(self, season: Season) -> int:
        """
        Calculate days remaining until the detected season ends.
        """
        if season == Season.YEAR_ROUND:
            return 365  # Always safe
        
        end_month, end_day = SEASON_END_DATES.get(season, (12, 31))
        
        # Construct end date for current or next year
        end_date = datetime(self.current_date.year, end_month, end_day)
        
        # If season already ended this year, check next year
        if end_date < self.current_date:
            end_date = datetime(self.current_date.year + 1, end_month, end_day)
        
        days_remaining = (end_date - self.current_date).days
        return max(0, days_remaining)
    
    def predict_velocity_decline(
        self, 
        product: Dict[str, Any],
        days_until_end: int,
        historical_orders: Optional[List[Dict]] = None
    ) -> float:
        """
        Predict the expected velocity decline percentage after season ends.
        
        Returns 0-1 representing expected decline (1 = 100% decline).
        """
        # Base decline based on seasonal strength
        base_decline = 0.5  # 50% default
        
        # Adjust based on days remaining
        if days_until_end < 7:
            urgency_factor = 0.3  # Very urgent
        elif days_until_end < 14:
            urgency_factor = 0.2
        elif days_until_end < 30:
            urgency_factor = 0.1
        else:
            urgency_factor = 0.0
        
        # Analyze historical data if available
        historical_factor = 0.0
        if historical_orders:
            # Check if product historically dies after season
            # (Simplified - in production would do proper time series analysis)
            order_dates = [o.get('created_at') for o in historical_orders if o.get('created_at')]
            if len(order_dates) > 5:
                # More orders in-season vs post-season suggests high decline
                historical_factor = 0.15
        
        # Calculate total decline prediction
        predicted_decline = min(0.95, base_decline + urgency_factor + historical_factor)
        
        return predicted_decline
    
    def assess_risk(
        self,
        product: Dict[str, Any],
        historical_orders: Optional[List[Dict]] = None
    ) -> SeasonalRisk:
        """
        Complete seasonal risk assessment for a product.
        """
        product_id = product.get('id', 'unknown')
        
        # Detect season
        season, season_confidence = self.detect_season(product)
        
        if season == Season.YEAR_ROUND:
            return SeasonalRisk(
                product_id=product_id,
                detected_season=season,
                days_until_season_end=365,
                risk_level='low',
                predicted_velocity_decline=0.1,
                confidence=0.5,
                reasoning="No seasonal patterns detected. Product appears year-round.",
                max_recommended_discount=0.15,
                clearance_window='pacing'
            )
        
        # Calculate timing
        days_until_end = self.calculate_days_until_season_end(season)
        
        # [HARDENED] Determine Window Policy
        window_policy = self._get_window_policy(days_until_end)
        
        # Predict velocity decline
        decline = self.predict_velocity_decline(product, days_until_end, historical_orders)
        
        # Determine risk level
        if days_until_end <= 7 and decline > 0.6:
            risk_level = 'critical'
        elif days_until_end <= 14 and decline > 0.5:
            risk_level = 'high'
        elif days_until_end <= 30:
            risk_level = 'moderate'
        else:
            risk_level = 'low'
        
        # Generate reasoning
        reasoning = self._generate_reasoning(
            product.get('title', 'Product'),
            season,
            days_until_end,
            decline,
            risk_level
        )
        
        return SeasonalRisk(
            product_id=product_id,
            detected_season=season,
            days_until_season_end=days_until_end,
            risk_level=risk_level,
            predicted_velocity_decline=decline,
            confidence=season_confidence,
            reasoning=reasoning,
            max_recommended_discount=window_policy['max_discount'],
            clearance_window=window_policy['name']
        )

    def _get_window_policy(self, days: int) -> Dict:
        """Returns the explicit policy for the current timeframe."""
        if days > 30:
            return {**SEASONAL_WINDOWS['pacing'], 'name': 'pacing'}
        elif days > 14:
            return {**SEASONAL_WINDOWS['urgency'], 'name': 'urgency'}
        else:
            return {**SEASONAL_WINDOWS['liquidation'], 'name': 'liquidation'}
    
    def _generate_reasoning(
        self,
        title: str,
        season: Season,
        days: int,
        decline: float,
        risk: str
    ) -> str:
        """Generate human-readable reasoning for the assessment."""
        reasoning = f"'{title}' detected as {season.value} seasonal product. "
        reasoning += f"{days} days until {season.value} ends. "
        reasoning += f"Expected {decline:.0%} velocity decline post-season. "
        
        if risk == 'critical':
            reasoning += "CRITICAL: Immediate clearance recommended."
        elif risk == 'high':
            reasoning += "High priority: Schedule clearance within 7 days."
        elif risk == 'moderate':
            reasoning += "Monitor closely. Consider clearance strategy."
        else:
            reasoning += "Low risk. Standard monitoring recommended."
        
        return reasoning
    
    @staticmethod
    def get_clearance_window(days_until_end: int) -> str:
        """
        Determine which clearance window applies.
        
        Returns: 'pre_season_end', 'season_end', or 'post_season'
        """
        if days_until_end > 30:
            return 'pre_season_end'
        elif days_until_end > 14:
            return 'season_end'
        else:
            return 'post_season'
