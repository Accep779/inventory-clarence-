# Strategy Agent: Multi-Plan Decision Flow

**Version**: 1.0 **Status**: Needs Migration to Parallel Execution
**Implementation**: `app.agents.strategy.StrategyAgent`

---

## 1. The Multi-Plan Philosophy

We do not just "pick a discount". We generate 3 fundamentally different
strategic approaches to clearing inventory.

| Plan Type        | Goal                   | Typical Strategy              | Target Audience            |
| :--------------- | :--------------------- | :---------------------------- | :------------------------- |
| **Conservative** | Protect Brand & Margin | _Loyalty Exclusive_, _Bundle_ | Champions, Loyal           |
| **Balanced**     | Maximize Sell-Through  | _Progressive Discount_        | At-Risk, Potential         |
| **Aggressive**   | Liquidity at any cost  | _Flash Sale_, _Liquidation_   | All Segments (Shock & Awe) |

---

## 2. Parallel Execution Flow (Required)

Current implementation is sequential. The required flow is **Parallel
Generation**:

```python
async def _select_multi_plan_strategy(self, product, session):
    # 1. PARALLEL GENERATION (Speed)
    # Each call uses a specific system prompt tuning (e.g. "You are a Brand Guardian")
    conservative, balanced, aggressive = await asyncio.gather(
        self._generate_plan(product, mode="conservative"),
        self._generate_plan(product, mode="balanced"),
        self._generate_plan(product, mode="aggressive")
    )
    
    # 2. CRITIC LOOP (Quality)
    # The Critic is NOT just an LLM. It is a Hybrid Logic/LLM evaluator.
    recommendation = await self._critic_loop({
        "conservative": conservative,
        "balanced": balanced,
        "aggressive": aggressive
    }, product)
    
    return recommendation
```

---

## 3. The Hybrid Critic Logic

The Critic must enforce **Hard Constraints** before engaging **Soft Reasoning**.

### Step A: Hard Filters (Deterministic)

Before asking the LLM, we disqualify plans that violate physics/finance.

1. **Floor Price Violation**: If `plan.price < product.floor_price`, DISQUALIFY.
2. **Margin Safety**: If `plan.margin < 0` AND strategy is not
   `aggressive_liquidation`, DISQUALIFY.
3. **Governor Limit**: If `plan.discount > merchant.max_auto_discount`,
   DISQUALIFY.

### Step B: Soft Reasoning (LLM)

If multiple plans survive Step A, the LLM Critic evaluates:

1. **Brand Alignment**: "Does a 'Flash Sale' hurt our 'Luxury' vibe?"
2. **History**: "Did 'Bundle' fail last time for this product?"
3. **Economics**: "Is holding cost > potential revenue loss?"

### Step C: Selection

- If **Critical Risk** (`severity=critical`): Prefer **Aggressive** (if valid).
- If **High Value** (`price > $100`): Prefer **Conservative** (preserve brand).
- Else: Prefer highest projected revenue (Balanced).
