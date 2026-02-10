# Production Scale Load Test

This directory contains the Locust load test script designed to validate
production readiness with 100 concurrent merchants.

## Prerequisites

1. **Environment**: Ensure the backend virtual environment is active and
   dependencies are installed.
   ```bash
   pip install locust jose
   ```

2. **Database Migrations**: Ensure the database schema is up to date.
   ```bash
   alembic upgrade head
   ```

3. **Seeding Data**: You MUST seed the database with the 100 test merchants
   before running the test. This script creates deterministic merchant data
   (IDs, products, proposals) that the load test relies on.
   ```bash
   python seed_load_test_data.py
   ```

## Running the Test

1. **Start the Server**:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

2. **Run Locust**: Run the test for the required 30 minutes (1800s) with 100
   users.
   ```bash
   locust -f tests/load/production_scale_test.py --headless -u 100 -r 2 -t 30m --host http://localhost:8000 --csv tests/load/results_production
   ```
   - `-u 100`: 100 concurrent users.
   - `-r 2`: Hatch rate (2 users/sec).
   - `-t 30m`: 30 minutes duration.

## Metrics & KPIs

The test verifies:

- **RPS**: Target 500-1000.
- **Latency**: p95 < 500ms, p99 < 1000ms.
- **Error Rate**: < 0.1%.
- **Fairness**: Simulates 100 distinct merchants.

## Results

After execution, Locust generates:

- `results_production_stats.csv`: Aggregate statistics.
- `results_production_failures.csv`: Error details.
- `results_production_history.csv`: Time-series data (RPS, Latency over time).
