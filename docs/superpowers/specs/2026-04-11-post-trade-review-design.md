# Post-Trade Review Modal — Design Spec
**Date:** 2026-04-11  
**Status:** Approved

---

## Overview

A post-trade review feature that surfaces closed-trade history with per-trade drill-down (entry thesis, factor scores, exit analysis, AI post-mortem) and aggregate pattern insights (win rate by regime, P&L by exit reason). Accessible from two entry points: the History tab in MatrixGrid and a new TRADES tab in the Intelligence Brief modal.

---

## Architecture

### Backend

**`GET /api/{portfolio_id}/trade-reviews`**

Joins three data sources to produce enriched closed-trade objects:
1. `transactions.csv` — pairs BUY + SELL records by ticker (only fully closed round-trips; open positions excluded)
2. `post_mortems.csv` — joined by ticker + close date for `what_worked`, `what_failed`, `recommendation`, `summary`
3. `daily_scores.jsonl` — looked up by ticker + entry date for factor scores; falls back to `factor_scores` field in BUY transaction if JSONL lookup misses

Returns the full enriched list in one response. No per-trade secondary fetch needed.

**`POST /api/{portfolio_id}/trade-reviews/{trade_id}/analyze`**

- `trade_id` is the BUY `transaction_id` (UUID from transactions.csv)
- Assembles a prompt: entry AI reasoning + factor scores at entry + exit reason + exit AI reasoning + P&L outcome + stored post-mortem
- Calls Claude Haiku
- Returns synthesized narrative string that explicitly connects entry thesis to exit outcome
- **Not persisted** — ephemeral response only

### Frontend Component Tree

```
IntelligenceBrief
  └── TradesTab (new 5th tab)
        ├── AggregatePanel     (left panel ~40%, top ~35% of left)
        ├── TradeList          (left panel ~40%, bottom ~65% of left)
        └── TradeDetail        (right panel ~60%)
```

**State:** Selected trade ID lives in local React state inside `TradesTab`. No Zustand store changes. History tab deep-link passes `{ openTab: 'TRADES', tradeId: string }` via the existing Intelligence Brief open mechanism.

---

## Left Panel

### AggregatePanel

**Row 1 — 4 stat chips:**
- Win Rate (% of closed trades with positive P&L)
- Avg P&L % (mean across all closed trades)
- Avg Hold Days
- Total Closed (count)

**Row 2 — 2 breakdown bars:**
- **By exit reason:** STOP LOSS / TAKE PROFIT / AI SELL / MANUAL — colored segments showing % of trades and avg P&L per bucket
- **By regime:** BULL / BEAR / SIDEWAYS — win rate per regime

### TradeList

**Columns:** Ticker | Close Date | Hold | P&L% | Exit Reason

- P&L% color-coded green/red
- Exit reason as small colored badge: red=STOP LOSS, green=TAKE PROFIT, blue=AI SELL, gray=MANUAL
- Default sort: close date descending; column headers are clickable to re-sort
- Filter bar: exit reason multi-select + date range (last 30d / 90d / all time)
- Selected row highlighted; clicking loads that trade in the right panel
- No pagination — scroll within panel (portfolios expected to have <200 closed trades)

---

## Right Panel — TradeDetail

**Empty state:** "Select a trade to review" placeholder when no trade is selected.

**When a trade is selected (top to bottom):**

### Header
- Ticker + entry date → exit date, hold days
- P&L $ and % in large text (green/red)
- Exit reason badge

### Entry Thesis
- AI reasoning from BUY `trade_rationale.ai_reasoning` as readable paragraph
- Labeled "Entry Thesis"
- Entry price, shares, stop loss, take profit as small chips below
- If no AI reasoning recorded: show "No AI reasoning recorded for this trade" placeholder

### Factor Scores at Entry
- Horizontal bar for each of the 6 factors: momentum, quality, earnings, volume, volatility, value_timing
- Score 0–100 displayed numerically and as bar fill
- Label: "Factors at Entry"

### Exit Analysis
- AI reasoning from SELL `trade_rationale.ai_reasoning`
- Below: `what_worked` and `what_failed` from post-mortem as two labeled blocks
- If no post-mortem row: omit `what_worked`/`what_failed` blocks silently; still show SELL AI reasoning

### Recommendation
- Stored `recommendation` field from post-mortem
- Omitted if not present

### Re-analyze Button
- Bottom of panel
- Calls `POST /trade-reviews/{trade_id}/analyze`
- Shows spinner while loading
- On success: returned narrative replaces the Entry Thesis + Exit Analysis + Recommendation sections
- On failure: inline error message "Analysis failed — try again"; panel state unchanged
- Re-analyzed content is clearly labeled "Re-analyzed" and is ephemeral (reverts on navigation away)

---

## Entry Points

### History Tab (MatrixGrid)
- Closed trade rows get `cursor: pointer`
- Clicking fires `openIntelligenceBrief({ tab: 'TRADES', tradeId: <buy_transaction_id> })`
- Intelligence Brief opens to TRADES tab with that trade pre-selected in the right panel

### Intelligence Brief
- "TRADES" added as 5th tab in tab bar: PERFORMANCE | RISK | FACTORS | GSCOTT | TRADES

---

## Error Handling & Edge Cases

| Scenario | Behavior |
|----------|----------|
| BUY with no matching SELL (still open) | Excluded from trade-reviews list entirely |
| No post-mortem row for a trade | Omit `what_worked`/`what_failed`/`recommendation` blocks; rest of detail renders normally |
| Empty `trade_rationale` (pre-AI trades) | Show "No AI reasoning recorded for this trade" placeholder in thesis/exit sections |
| Re-analyze API failure or timeout | Inline error in detail panel; panel content unchanged |
| No closed trades yet | Aggregate shows zeroed stats + "No closed trades yet" empty state; right panel empty |
| Same ticker bought/sold multiple times | Each round-trip is a separate list entry, distinguished by entry date |

---

## Data Contract

### Enriched Closed Trade Object (returned by GET /trade-reviews)

```json
{
  "trade_id": "132dd93d-...",
  "ticker": "RCKT",
  "entry_date": "2026-03-24",
  "exit_date": "2026-03-27",
  "holding_days": 3,
  "entry_price": 4.32,
  "exit_price": 4.36,
  "shares": 553,
  "stop_loss": 4.02,
  "take_profit": 21.60,
  "pnl": 22.12,
  "pnl_pct": 0.93,
  "exit_reason": "STOP_LOSS",
  "regime_at_entry": "SIDEWAYS",
  "regime_at_exit": "SIDEWAYS",
  "entry_ai_reasoning": "Clinical-stage biotech...",
  "exit_ai_reasoning": "Layer 1 mechanical sell...",
  "factor_scores": {
    "momentum": 66.0,
    "quality": 50.0,
    "earnings": 50.0,
    "volume": 70.5,
    "volatility": 82.0,
    "value_timing": 55.3
  },
  "what_worked": "...",
  "what_failed": "...",
  "recommendation": "...",
  "summary": "..."
}
```

### Re-analyze Response

```json
{
  "narrative": "RCKT was bought on a gene therapy catalyst thesis with strong volatility signal (82)..."
}
```

---

## Out of Scope

- Persisting re-analyzed narratives
- Intraday price charts for the hold period
- Cross-portfolio trade comparison
- Exporting trade history to CSV
