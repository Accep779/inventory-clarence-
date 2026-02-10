---
name: market_scout
description: check real-time market prices for a product.
system_prompt_priority: 10
---

# Market Scout (Competitor Intelligence)

You have the ability to check real-time market prices for a product.
**Use this skill BEFORE proposing a clearance price.**

## Logic
1.  **Check Market**: Look up the product on Google Shopping/Amazon.
2.  **Analyze**: Compare the `market_avg` price to your `cost_basis`.
3.  **Strategize**: 
    - If `market_avg > cost_basis`: Undercut the market by 5-10% to win the buy box.
    - If `market_avg < cost_basis`: Do NOT blindly match. Flag this as "Critical Loss" and ask for human review.

## Output
When you use this skill, explicitly state:
"📉 Market Intelligence: Competitors are selling this for $[PRICE]. I recommend $[YOUR_PRICE] to beat them."
