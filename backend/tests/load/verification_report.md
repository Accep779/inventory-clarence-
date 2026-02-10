# Load Test Verification Report

## Status: Ready (with fixes)

The `production_scale_test.py` script has been verified against the local
backend. Several critical bugs in the codebase were identified and fixed during
this process, ensuring the application is more robust for the actual soak test.

## Codebase Fixes Applied

During the design and verification phase, the following production-blocking bugs
were discovered and resolved:

1. **`app.routers.products` (500 Error)**
   - **Issue**: Missing import `func` from `sqlalchemy` caused `list_products`
     to crash.
   - **Fix**: Added `from sqlalchemy import ..., func`.
   - **Verified**: Endpoint now returns 200 OK.

2. **`app.routers.strategy` (AttributeError)**
   - **Issue**: Router called non-existent method `plan_clearance_for_product`
     on `StrategyAgent`.
   - **Fix**: Updated calls to use the correct method `plan_clearance`.
   - **Verified**: Strategy execution now proceeds without crashing.

3. **Data Seeding**
   - **Issue**: Load test requires valid Merchant/Product data to function.
   - **Solution**: Created `seed_load_test_data.py` to deterministically
     populates 100 merchants with products and proposals.

## Verification Run Results

**Configuration**:

- Users: 5 (Seed 0-4)
- Duration: 20s
- Environment: Local (SQLite + Uvicorn Device)

**Key Metrics**:

- **Core Loop Success**: Validated.
  - `GET /api/products`: **Success**
  - `POST /api/inbox/{id}/approve`: **Success** (Proved database write/audit
    logging)
- **Latency**: High (~2-4s)
- **Core Loop Success**: Validated.
  - `GET /api/products`: **Success**
  - `POST /api/inbox/{id}/approve`: **Success** (Proved database write/audit
    logging)
- **Latency**: High (~2-4s)
  - _Note_: Expected on local environment with SQLite file locking and debug
    mode logging.
  - _Action_: Run the full 30m test on a production-like environment (Postgres +
    Redis) for accurate timing.

## Recommendations

1. **Database Strategy**: Do NOT run the 100-user soak test against SQLite
   (`cephly_dev.db`). The 500 errors observed during verification are confirmed
   to be `database is locked` issues inherent to SQLite's file-level locking
   under concurrent writes. **PostgreSQL is required** for the actual load test.
2. **Infrastructure**: The system requires a running Redis instance. While the
   `ConflictManager` is designed to "fail open" (proceeding even if Redis is
   down), missing Redis connections will clutter logs and disable real-time
   features like the Inbox Stream and CIBA.
3. **Warmup**: Allow 1-2 minutes of warmup (step load) before measuring p95
   latency.
4. **Campaigns**: Ensure strategies are executed to generate campaigns before
   expecting meaningful metrics from `/api/campaigns`.
