# backend/tests/test_seasonal_agent.py
"""
Unit Tests for Seasonal Transition Agent
=========================================

Tests cover all 7 world-class patterns:
1. Season detection accuracy
2. Risk assessment logic
3. Strategy selection with memory
4. Plan-Criticize-Act pattern
5. Self-verification
6. Failure reflection integration
7. Continuous learning
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.seasonal_analyzer import (
    SeasonalAnalyzer, 
    Season, 
    SeasonalRisk
)
from app.agents.seasonal_transition import SeasonalTransitionAgent


class TestSeasonalAnalyzer:
    """Test the pure analysis service."""
    
    def setup_method(self):
        # Fix date to January 20, 2024 for consistent testing
        self.analyzer = SeasonalAnalyzer(
            current_date=datetime(2024, 1, 20)
        )
    
    def test_detect_summer_product(self):
        """Summer keywords should detect summer season."""
        product = {
            'id': 'test-1',
            'title': 'Beach Umbrella Summer Collection',
            'description': 'Perfect for pool and outdoor use',
            'tags': ['summer', 'beach', 'outdoor']
        }
        
        season, confidence = self.analyzer.detect_season(product)
        
        assert season == Season.SUMMER
        assert confidence > 0.5
    
    def test_detect_winter_product(self):
        """Winter keywords should detect winter season."""
        product = {
            'id': 'test-2',
            'title': 'Winter Parka Jacket',
            'description': 'Keep warm in the snow',
            'tags': ['winter', 'coat', 'warm']
        }
        
        season, confidence = self.analyzer.detect_season(product)
        
        assert season == Season.WINTER
        assert confidence > 0.5
    
    def test_detect_holiday_product(self):
        """Holiday keywords should detect holiday season."""
        product = {
            'id': 'test-3',
            'title': 'Christmas Ornament Gift Set',
            'description': 'Perfect holiday gift',
            'tags': ['christmas', 'holiday', 'gift']
        }
        
        season, confidence = self.analyzer.detect_season(product)
        
        assert season == Season.HOLIDAY
        assert confidence > 0.5
    
    def test_detect_year_round_product(self):
        """Products without seasonal keywords return YEAR_ROUND."""
        product = {
            'id': 'test-4',
            'title': 'USB Cable',
            'description': 'Standard charging cable',
            'tags': ['electronics', 'cable']
        }
        
        season, confidence = self.analyzer.detect_season(product)
        
        assert season == Season.YEAR_ROUND
        assert confidence == 0.0
    
    def test_days_until_summer_end(self):
        """Should calculate days until September 22."""
        days = self.analyzer.calculate_days_until_season_end(Season.SUMMER)
        
        # From Jan 20, 2024 to Sep 22, 2024 = 246 days
        assert days > 200
        assert days < 300
    
    def test_days_until_winter_end(self):
        """Should calculate days until March 20."""
        days = self.analyzer.calculate_days_until_season_end(Season.WINTER)
        
        # From Jan 20, 2024 to Mar 20, 2024 = 60 days
        assert days > 50
        assert days < 70
    
    def test_velocity_decline_urgency(self):
        """Products with fewer days should have higher decline."""
        product = {'id': 'test', 'title': 'Test'}
        
        decline_urgent = self.analyzer.predict_velocity_decline(product, days_until_end=5)
        decline_normal = self.analyzer.predict_velocity_decline(product, days_until_end=60)
        
        assert decline_urgent > decline_normal
    
    def test_full_risk_assessment(self):
        """Full risk assessment should return complete SeasonalRisk."""
        product = {
            'id': 'test-summer',
            'title': 'Summer Beach Towel',
            'description': 'Pool side essential',
            'tags': ['summer', 'beach']
        }
        
        risk = self.analyzer.assess_risk(product)
        
        assert isinstance(risk, SeasonalRisk)
        assert risk.product_id == 'test-summer'
        assert risk.detected_season == Season.SUMMER
        assert risk.days_until_season_end > 0
        assert risk.risk_level in ['critical', 'high', 'moderate', 'low']
        assert 0 <= risk.predicted_velocity_decline <= 1
        assert len(risk.reasoning) > 0
    
    def test_clearance_window_classification(self):
        """Clearance windows should be classified correctly."""
        assert SeasonalAnalyzer.get_clearance_window(45) == 'pre_season_end'
        assert SeasonalAnalyzer.get_clearance_window(20) == 'season_end'
        assert SeasonalAnalyzer.get_clearance_window(10) == 'post_season'
        assert SeasonalAnalyzer.get_clearance_window(5) == 'post_season'


class TestSeasonalTransitionAgent:
    """Test the agent with mocked dependencies."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        return session
    
    @pytest.fixture
    def agent(self):
        """Create agent instance."""
        return SeasonalTransitionAgent(merchant_id='test-merchant')
    
    @pytest.mark.asyncio
    async def test_fallback_strategy_urgency(self, agent):
        """Fallback should return aggressive strategy for urgent cases."""
        from app.services.seasonal_analyzer import SeasonalRisk, Season
        
        urgent_risk = SeasonalRisk(
            product_id='test',
            detected_season=Season.SUMMER,
            days_until_season_end=5,
            risk_level='critical',
            predicted_velocity_decline=0.8,
            confidence=0.9,
            reasoning='Test'
        )
        
        strategy = agent._fallback_strategy(urgent_risk, 'post_season')
        
        assert strategy == 'aggressive_liquidation'
    
    @pytest.mark.asyncio
    async def test_fallback_strategy_moderate(self, agent):
        """Fallback should return moderate strategy for less urgent cases."""
        from app.services.seasonal_analyzer import SeasonalRisk, Season
        
        moderate_risk = SeasonalRisk(
            product_id='test',
            detected_season=Season.SUMMER,
            days_until_season_end=45,
            risk_level='moderate',
            predicted_velocity_decline=0.3,
            confidence=0.7,
            reasoning='Test'
        )
        
        strategy = agent._fallback_strategy(moderate_risk, 'pre_season_end')
        
        assert strategy == 'progressive_discount'


class TestWorldClassPatterns:
    """
    Verify the 7 world-class patterns are present in the agent.
    """
    
    def test_pattern_1_dual_memory(self):
        """Agent should use MemoryService for episodic and semantic memory."""
        import inspect
        from app.agents.seasonal_transition import SeasonalTransitionAgent
        
        source = inspect.getsource(SeasonalTransitionAgent._select_strategy)
        
        assert 'recall_campaign_outcomes' in source, "Missing episodic memory"
        assert 'get_merchant_preferences' in source, "Missing semantic memory"
    
    def test_pattern_2_plan_criticize_act(self):
        """Agent should have self-criticism method."""
        from app.agents.seasonal_transition import SeasonalTransitionAgent
        
        assert hasattr(SeasonalTransitionAgent, '_criticize_strategy')
        
        import inspect
        source = inspect.getsource(SeasonalTransitionAgent._criticize_strategy)
        assert 'approval' in source.lower()
        assert 'concerns' in source.lower()
    
    def test_pattern_3_self_verification(self):
        """Agent should have verification method."""
        from app.agents.seasonal_transition import SeasonalTransitionAgent
        
        assert hasattr(SeasonalTransitionAgent, '_verify_proposal')
        
        import inspect
        source = inspect.getsource(SeasonalTransitionAgent._verify_proposal)
        assert 'verified' in source.lower()
        assert 'issues' in source.lower()
    
    def test_pattern_4_transparent_reasoning(self):
        """Agent should log all reasoning via ThoughtLogger."""
        import inspect
        from app.agents.seasonal_transition import SeasonalTransitionAgent
        
        source = inspect.getsource(SeasonalTransitionAgent.plan_seasonal_clearance)
        
        assert 'ThoughtLogger.log_thought' in source
        assert 'observation' in source or 'decision' in source
    
    def test_pattern_5_task_decomposition(self):
        """Agent should handle 3 clearance windows."""
        import inspect
        from app.agents.seasonal_transition import SeasonalTransitionAgent
        
        source = inspect.getsource(SeasonalTransitionAgent._select_strategy)
        
        assert 'pre_season_end' in source or 'clearance_window' in source
    
    def test_pattern_6_failure_reflection(self):
        """Agent should integrate with FailureReflector."""
        import inspect
        from app.agents.seasonal_transition import SeasonalTransitionAgent
        
        source = inspect.getsource(SeasonalTransitionAgent._select_strategy)
        
        assert 'FailureReflector' in source or 'get_accumulated_lessons' in source
    
    def test_pattern_7_continuous_learning(self):
        """Agent should use accumulated lessons in prompts."""
        import inspect
        from app.agents.seasonal_transition import SeasonalTransitionAgent
        
        source = inspect.getsource(SeasonalTransitionAgent._select_strategy)
        
        assert 'lessons' in source.lower()
        assert 'past' in source.lower() or 'failure' in source.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
