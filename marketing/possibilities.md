# design: "Ralph-Style" Autonomous Goal-Seeking Agent

## Concept

The user wants a "Fire and Forget" agent. Instead of approving every single
campaign, the merchant sets a **Goal** (e.g., "Clear 50% of this SKU") and
constraints (Min Price $20), and the agent loops autonomously until the goal is
met.

We will implement this using the **"Ralph Loop" Pattern** on top of our new
Temporal infrastructure.

## Architecture

### 1. The Goal (Input)

```json
{
    "product_id": "123",
    "goal_type": "inventory_reduction",
    "target_value": 50, // Reduce by 50 units
    "constraints": {
        "min_floor_price": 19.99,
        "max_daily_spend": 500,
        "max_iterations": 10
    }
}
```

### 2. The Loop (Temporal Workflow)

**Name:** `GoalSeekingWorkflow` **Logic:**

```python
while current_inventory > target_inventory:
    # 1. PLAN: Strategy Agent proposes an action (e.g., "Flash Sale 20% off")
    strategy = await execute_activity("strategy_agent_plan", ...)
    
    # 2. ACT: Execution Agent runs the campaign
    result = await execute_activity("execute_campaign", ...)
    
    # 3. OBSERVE (Feedback): Wait 24h, then check sales
    await workflow.sleep(timedelta(hours=24))
    sales = await execute_activity("check_sales_lift", ...)
    
    # 4. LEARN: Update 'Strategy Memory' with result
    await execute_activity("record_learning", {strategy: strategy, result: sales})
    
    # 5. RETRY: Loop continues with new context (Strategy Agent sees previous failure)
```

## Implementation Steps

### Phase 1: The Workflow (Backend)

- [ ] Create `backend/app/workflows/goal_seeking.py`
- [ ] Implement the "Plan -> Act -> Wait -> Observe" loop.
- [ ] Add `check_sales_lift` activity (Integrate with Shopify Orders).

### Phase 2: The UI (Frontend)

- [ ] New Page: `pages/goals.tsx`
- [ ] Simple Form: Select Product -> Set Goal -> "Start Autonomous Agent".
- [ ] Status Panel: Shows "Current Iteration: 3/10", "Units Sold: 12/50".

## Why Temporal?

- **Durability:** This loop takes _weeks_. Temporal handles the 24h sleeps and
  reboots perfectly.
- **State:** Temporal stores the "Current Progress" automatically.

## Estimated Effort

- Backend Workflow: 1 Day
- Frontend UI: 1 Day
- Testing: 1 Day
