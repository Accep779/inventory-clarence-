# app/services/phase_executor.py
"""
Phase Executor Service
======================

WORLD-CLASS PATTERN: Task Decomposition.

Instead of executing campaigns all-at-once, we break them into phases:
- Phase 1: Test with small audience (10%)
- Phase 2: Analyze results
- Phase 3: Scale if successful, or pivot strategy

Inspired by: BabyAGI's task creation → execution → reprioritization loop.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.database import async_session_maker
from app.models import Campaign, InboxItem

logger = logging.getLogger(__name__)


class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    PIVOTING = "pivoting"


@dataclass
class PhaseConfig:
    """Configuration for a campaign phase."""
    phase_number: int
    audience_percent: float  # 0.1 = 10%
    duration_hours: int
    success_threshold: float  # Minimum open rate to proceed
    name: str


# Default phase configuration (BabyAGI-inspired progressive rollout)
DEFAULT_PHASES = [
    PhaseConfig(1, 0.10, 24, 0.10, "Test Group"),      # 10% for 24h, need 10% open rate
    PhaseConfig(2, 0.30, 48, 0.12, "Validation Group"), # 30% for 48h, need 12% open rate  
    PhaseConfig(3, 1.00, 72, 0.00, "Full Rollout"),     # 100% for 72h, no threshold (final)
]


class PhaseExecutor:
    """
    Manages phased campaign execution.
    
    This implements the Task Decomposition pattern by:
    1. Breaking a campaign into phases
    2. Executing each phase sequentially
    3. Analyzing results between phases
    4. Pivoting strategy if phase fails
    """
    
    def __init__(self, merchant_id: str, phases: List[PhaseConfig] = None):
        self.merchant_id = merchant_id
        self.phases = phases or DEFAULT_PHASES
    
    async def execute_phased_campaign(
        self, 
        campaign_id: str,
        execute_phase_func: callable
    ) -> Dict[str, Any]:
        """
        Execute a campaign in phases.
        
        Args:
            campaign_id: The campaign to execute
            execute_phase_func: Async function that executes a phase
                               Signature: (campaign, phase_config) -> bool
        
        Returns:
            Final execution result with phase history
        """
        from app.services.thought_logger import ThoughtLogger
        
        phase_history = []
        current_phase = 0
        
        async with async_session_maker() as session:
            campaign = await session.get(Campaign, campaign_id)
            if not campaign:
                raise ValueError(f"Campaign {campaign_id} not found")
            
            # Initialize phase tracking
            campaign.metadata_json = campaign.metadata_json or {}
            campaign.metadata_json['phased_execution'] = {
                'enabled': True,
                'current_phase': 0,
                'phase_history': []
            }
            
            await ThoughtLogger.log_thought(
                merchant_id=self.merchant_id,
                agent_type="execution",
                thought_type="planning",
                summary=f"Starting phased execution: {len(self.phases)} phases planned",
                detailed_reasoning={
                    'campaign_id': campaign_id,
                    'phases': [
                        {'phase': p.phase_number, 'audience': f"{p.audience_percent:.0%}", 'duration': f"{p.duration_hours}h"}
                        for p in self.phases
                    ]
                }
            )
            
            for phase in self.phases:
                current_phase = phase.phase_number
                
                # Log phase start
                await ThoughtLogger.log_thought(
                    merchant_id=self.merchant_id,
                    agent_type="execution",
                    thought_type="action",
                    summary=f"Phase {phase.phase_number}: Executing '{phase.name}' ({phase.audience_percent:.0%} audience)",
                    detailed_reasoning={
                        'phase': phase.phase_number,
                        'audience_percent': phase.audience_percent,
                        'success_threshold': phase.success_threshold
                    }
                )
                
                # Execute the phase
                phase_result = await execute_phase_func(campaign, phase)
                
                phase_record = {
                    'phase': phase.phase_number,
                    'name': phase.name,
                    'started_at': datetime.utcnow().isoformat(),
                    'audience_percent': phase.audience_percent,
                    'success': phase_result.get('success', False),
                    'metrics': phase_result.get('metrics', {})
                }
                phase_history.append(phase_record)
                
                # Analyze phase results (except for final phase)
                if phase.phase_number < len(self.phases):
                    analysis = await self._analyze_phase(campaign, phase, phase_result)
                    
                    if not analysis['should_continue']:
                        # Phase failed threshold - need to pivot
                        await ThoughtLogger.log_thought(
                            merchant_id=self.merchant_id,
                            agent_type="execution",
                            thought_type="decision",
                            summary=f"Phase {phase.phase_number} did not meet threshold. Recommending pivot.",
                            detailed_reasoning={
                                'actual_rate': analysis.get('actual_rate', 0),
                                'required_rate': phase.success_threshold,
                                'recommendation': analysis.get('recommendation', 'pivot')
                            }
                        )
                        
                        return {
                            'status': 'pivot_recommended',
                            'completed_phases': current_phase,
                            'phase_history': phase_history,
                            'pivot_reason': analysis.get('reason', 'Below threshold')
                        }
            
            # All phases completed successfully
            await ThoughtLogger.log_thought(
                merchant_id=self.merchant_id,
                agent_type="execution",
                thought_type="decision",
                summary=f"Phased execution complete. All {len(self.phases)} phases succeeded.",
                detailed_reasoning={'phase_history': phase_history}
            )
            
            return {
                'status': 'completed',
                'completed_phases': len(self.phases),
                'phase_history': phase_history
            }
    
    async def _analyze_phase(
        self, 
        campaign: Campaign, 
        phase: PhaseConfig,
        phase_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze phase results to decide whether to continue.
        
        This is the "Task Prioritization" step from BabyAGI -
        evaluating completed work before proceeding.
        """
        metrics = phase_result.get('metrics', {})
        
        # Calculate open rate
        emails_sent = metrics.get('emails_sent', 1)
        emails_opened = metrics.get('emails_opened', 0)
        open_rate = emails_opened / emails_sent if emails_sent > 0 else 0
        
        # Check against threshold
        passes_threshold = open_rate >= phase.success_threshold
        
        return {
            'should_continue': passes_threshold,
            'actual_rate': open_rate,
            'required_rate': phase.success_threshold,
            'reason': 'Passed threshold' if passes_threshold else f'Open rate {open_rate:.1%} below {phase.success_threshold:.1%}',
            'recommendation': 'continue' if passes_threshold else 'pivot'
        }
    
    async def get_phase_status(self, campaign_id: str) -> Dict[str, Any]:
        """Get current phase status for a campaign."""
        async with async_session_maker() as session:
            campaign = await session.get(Campaign, campaign_id)
            if not campaign:
                return {'error': 'Campaign not found'}
            
            phased_data = (campaign.metadata_json or {}).get('phased_execution', {})
            
            return {
                'enabled': phased_data.get('enabled', False),
                'current_phase': phased_data.get('current_phase', 0),
                'total_phases': len(self.phases),
                'phase_history': phased_data.get('phase_history', [])
            }
