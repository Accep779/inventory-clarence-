import sys
import os
from unittest.mock import MagicMock

# Mock Environment BEFORE imports
os.environ["TOKEN_ENCRYPTION_KEY"] = "mock_key_for_testing_purposes_only_32b"

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.services.seasonal_analyzer import SeasonalAnalyzer, Season

def test_seasonal_windows():
    print("[TEST] Verifying Seasonal Urgency Windows...")
    
    analyzer = SeasonalAnalyzer()
    
    # Mock Product
    product = {"id": "p1", "title": "Winter Coat", "product_type": "Outerwear"}
    
    # Inject deterministic timing override by mocking calculation
    # Only mocking the internal day calc, assuming 'Winter' is detected or we force it
    
    # Force 'Winter' detection
    analyzer.detect_season = MagicMock(return_value=(Season.WINTER, 0.9))
    
    # Case 1: Pacing (>30 Days)
    analyzer.calculate_days_until_season_end = MagicMock(return_value=60)
    res = analyzer.assess_risk(product)
    if res.clearance_window == 'pacing' and res.max_recommended_discount == 0.20:
        print("   [PASS]: Pacing Window (Max 20%)")
    else:
        print(f"   [FAIL]: Pacing Window mismatch. Got {res.clearance_window}, {res.max_recommended_discount}")

    # Case 2: Liquidation (<14 Days)
    analyzer.calculate_days_until_season_end = MagicMock(return_value=5)
    res = analyzer.assess_risk(product)
    if res.clearance_window == 'liquidation' and res.max_recommended_discount == 0.75:
        print("   [PASS]: Liquidation Window (Max 75%)")
    else:
        print(f"   [FAIL]: Liquidation Window mismatch. Got {res.clearance_window}, {res.max_recommended_discount}")

if __name__ == "__main__":
    test_seasonal_windows()
