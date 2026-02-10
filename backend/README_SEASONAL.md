# Seasonal Transition Agent

A world-class AI agent that identifies seasonal inventory risks and proactively
generates clearance strategies before stock becomes dead weight.

## Overview

The Seasonal Transition Agent implements all 7 world-class agent patterns:

| Pattern               | Implementation                                 |
| --------------------- | ---------------------------------------------- |
| Dual Memory           | `MemoryService` for episodic + semantic recall |
| Plan-Criticize-Act    | `_criticize_strategy()` before execution       |
| Self-Verification     | `_verify_proposal()` after creation            |
| Transparent Reasoning | `ThoughtLogger` throughout                     |
| Task Decomposition    | 3 clearance windows (pre/end/post)             |
| Failure Reflection    | `FailureReflector` integration                 |
| Continuous Learning   | Lessons in strategy prompts                    |

## Files Created

```
backend/
├── app/
│   ├── agents/
│   │   └── seasonal_transition.py    # Core agent
│   ├── services/
│   │   └── seasonal_analyzer.py      # Season detection service
│   ├── tasks/
│   │   └── seasonal_scan.py          # Celery background task
│   └── routers/
│       └── seasonal.py               # API endpoints
└── tests/
    └── test_seasonal_agent.py        # Unit tests

new_frontend/
└── components/
    └── seasonal/
        ├── SeasonalRiskCard.tsx       # Risk display with countdown
        ├── SeasonalInsights.tsx       # Performance visualization
        ├── SeasonalSettings.tsx       # Configuration UI
        └── index.ts                   # Barrel exports
```

## API Endpoints

### GET /api/seasonal/risks

List products with seasonal risk assessments.

```bash
curl -X GET "http://localhost:8000/api/seasonal/risks?season=summer&risk_level=high" \
  -H "Authorization: Bearer $TOKEN"
```

### POST /api/seasonal/scan

Trigger manual seasonal scan.

```bash
curl -X POST "http://localhost:8000/api/seasonal/scan" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"async_mode": true}'
```

### GET /api/seasonal/insights

Get historical seasonal performance.

```bash
curl -X GET "http://localhost:8000/api/seasonal/insights" \
  -H "Authorization: Bearer $TOKEN"
```

## Agent Flow

```
1. DETECT    → Analyze product metadata for seasonal keywords
2. ASSESS    → Calculate days until season end, predict velocity decline
3. PLAN      → Select clearance strategy using LLM + Memory
4. CRITICIZE → Self-critique strategy selection
5. REVISE    → Pivot if criticism rejected
6. PRICE     → Calculate with floor constraints
7. COPY      → Generate campaign copy via LLM
8. PROJECT   → Revenue vs holding cost analysis
9. PROPOSE   → Create InboxItem for merchant approval
10. VERIFY   → Check proposal completeness
```

## Celery Schedule

Add to `worker.py`:

```python
'weekly-seasonal-scan': {
    'task': 'app.tasks.seasonal_scan.run_weekly_seasonal_scan',
    'schedule': crontab(day_of_week='sunday', hour=2, minute=0)
}
```

## Running Tests

```bash
cd backend
pytest tests/test_seasonal_agent.py -v
```

## Register Router

Add to `main.py`:

```python
from app.routers.seasonal import router as seasonal_router
app.include_router(seasonal_router)
```
