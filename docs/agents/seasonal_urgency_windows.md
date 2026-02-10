# Seasonal Agent: Urgency Windows & Discount Logic

**Version**: 1.0 **Status**: Implicit -> Needs Explicit Config
**Implementation**: `app.services.seasonal_analyzer.SeasonalAnalyzer`

---

## 1. The Urgency Philosophy

Seasonal clearance is a function of **Time Remaining**. As the end of the season
approaches, the "Value of Holding" drops to zero (or negative due to storage
costs), so the "Willingness to Discount" must increase exponentially.

---

## 2. The Season Schedules (Global Config)

We define seasons with fixed dates (Northern Hemisphere Default), but allow
per-merchant overrides.

| Season      | Start Date | End Date | Key Keywords                  |
| :---------- | :--------- | :------- | :---------------------------- |
| **Winter**  | Dec 1      | Feb 28   | Coat, Snow, Fleece, Christmas |
| **Spring**  | Mar 1      | May 31   | Floral, Pastel, Rain, Light   |
| **Summer**  | Jun 1      | Aug 31   | Swim, Short, Sandal, Beach    |
| **Fall**    | Sep 1      | Nov 30   | Pumpkin, Sweater, Halloween   |
| **Holiday** | Nov 1      | Dec 26   | Gift, Ornament, Party         |

---

## 3. The Three Clearance Windows

For any product detected as belonging to the _Current Season_, we determine its
window.

### Window 1: Pacing (Pre-End)

- **Trigger**: > 30 Days until Season End.
- **Strategy**: "Preserve Margin".
- **Discount Cap**: **Max 20%**.
- **Goal**: Clear inventory without training customers to wait for crashes.

### Window 2: Urgency (Season-End)

- **Trigger**: 14 - 30 Days until Season End.
- **Strategy**: "Recover Cash".
- **Discount Cap**: **Max 40%**.
- **Goal**: Aggressive clearing. The item will be dead stock in 2 weeks.

### Window 3: Liquidation (Post-Season / Late)

- **Trigger**: < 14 Days until End OR Post-Season.
- **Strategy**: "Evacuation".
- **Discount Cap**: **Max 75%** (or Cost).
- **Goal**: Vacate warehouse space. Revenue is secondary to storage cost
  removal.

---

## 4. Logic Override: Low Inventory

- **Rule**: If `Inventory < 10 Units`, **IGNORE** the Clearance Window.
- **Action**: Do not liquidate. Let it sell naturally or use `Bundle_Promotion`.
- _Reasoning_: Low stock doesn't justify a "Campaign". It creates customer
  frustration if it sells out in seconds.
