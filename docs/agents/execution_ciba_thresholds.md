# Execution Agent: CIBA Threshold Policies

**Version**: 1.0 **Status**: Implemented / Needs External Config
**Implementation**: `app.services.ciba_service` & `app.agents.execution`

---

## 1. The CIBA Philosophy

**Client Initiated Back-Channel Authentication (CIBA)** is our "Safety Valve".
It stops the AI from making catastrophic mistakes by asking for human permission
via Push/SMS when specific risk thresholds are breached.

---

## 2. Hard Trigger Thresholds

The Execution Agent MUST trigger CIBA if **ANY** of the following validation
rules evaluate to TRUE.

| Metric            | Threshold                                     | Rationale                                  |
| :---------------- | :-------------------------------------------- | :----------------------------------------- |
| **Max Discount**  | `> Merchant.max_auto_discount` (Default: 40%) | Honor merchant profitability guardrails.   |
| **Total Spend**   | `> Merchant.max_daily_budget` (Default: $500) | Prevent runaway ad spend.                  |
| **Audience Size** | `> 2,000 Customers` (Batch)                   | Prevent mass-spam incidents.               |
| **New Merchant**  | `Merchant.age < 14 Days`                      | "Training Wheels" protocol to build trust. |
| **High Value**    | `Inventory Value > $10,000`                   | High financial stakes require human eyes.  |

---

## 3. The Notification Flow (Service Level Agreement)

When CIBA is triggered, the `CIBAService` must adhere to this escalation ladder
to ensure vital decisions aren't missed:

1. **Immediate (T+0s)**: Send **Push Notification** to Merchant Mobile App.
   - _Content_: "Approval Needed: Flash Sale on [Product] ($12k Value)"
2. **Fallback (T+5m)**: If not resolved, send **SMS with Magic Link**.
   - _Why_: SMS has 98% open rate but costs money.
3. **Governance (T+30m)**: If still pending, **Auto-Pause** execution and log
   "Timeout".
   - _Reasoning_: Better to miss a sale than execute an unapproved risky
     campaign.

---

## 4. Timeout Handling

- **Default Timeout**: 30 Minutes.
- **Action on Timeout**:
  1. Mark Campaign as `blocked_authorization_timeout`.
  2. Notify Merchant: "Campaign paused due to lack of response."
  3. **Do NOT auto-approve**. Silence is NOT consent in high-stakes finance.
