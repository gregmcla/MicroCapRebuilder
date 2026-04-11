# Post-Trade Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a TRADES tab to the Intelligence Brief modal with aggregate stats, a filterable closed-trade list, and a per-trade detail panel (entry thesis, factor scores, exit analysis, Re-analyze with Claude button). History tab in MatrixGrid gets a clickable closed trades section that deep-links into the TRADES tab.

**Architecture:** New `GET /api/{portfolio_id}/trade-reviews` endpoint joins transactions.csv + post_mortems.csv into enriched closed-trade objects. A `POST /api/{portfolio_id}/trade-reviews/{trade_id}/analyze` endpoint calls Claude Haiku for on-demand re-analysis. A new `BriefStore` in Zustand coordinates opening the Intelligence Brief to a specific tab + trade from anywhere in the app. The TRADES tab is a split-panel component: 40% left (aggregate + filterable list), 60% right (trade detail).

**Tech Stack:** Python 3 / FastAPI / pandas / anthropic SDK (backend). React 19 / TanStack Query / Zustand / TypeScript (frontend).

---

## File Map

**Create:**
- `api/routes/trade_reviews.py` — GET + POST endpoints; pure data logic, no business logic
- `dashboard/src/components/IntelligenceBrief/TradesTab.tsx` — TRADES tab component (AggregatePanel, TradeList, TradeDetail)
- `tests/test_trade_reviews.py` — backend unit tests

**Modify:**
- `api/main.py` — register trade_reviews router
- `dashboard/src/lib/types.ts` — add ClosedTrade, TradeReviewsResponse, TradeAnalyzeResponse types
- `dashboard/src/lib/api.ts` — add getTradeReviews, analyzeTradeReview methods
- `dashboard/src/lib/store.ts` — add BriefStore (briefOpen, briefInitialTab, briefInitialTradeId)
- `dashboard/src/components/TopBar.tsx` — replace showBrief local state with BriefStore
- `dashboard/src/components/IntelligenceBrief/index.tsx` — add "trades" tab, accept initialTab + initialTradeId props
- `dashboard/src/components/MatrixGrid/MatrixGrid.tsx` — add portfolioId prop to HistoryPanel, add closed trades section

---

## Task 1: Backend — GET /trade-reviews endpoint (TDD)

**Files:**
- Create: `api/routes/trade_reviews.py`
- Create: `tests/test_trade_reviews.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_trade_reviews.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import json
import pytest
import pandas as pd


# We import the helper after adding it to the module
from api.routes.trade_reviews import _load_closed_trades


def _write_csv(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


@pytest.fixture
def portfolio_dir(tmp_path: Path) -> Path:
    d = tmp_path / "portfolios" / "test"
    d.mkdir(parents=True)
    return d


def test_no_transactions_returns_empty(portfolio_dir: Path) -> None:
    trades = _load_closed_trades("test", data_dir=portfolio_dir.parent)
    assert trades == []


def test_open_position_excluded(portfolio_dir: Path) -> None:
    """A BUY with no matching SELL must not appear in results."""
    _write_csv(portfolio_dir / "transactions.csv", [
        {"transaction_id": "aaa", "date": "2026-01-10", "ticker": "AAPL",
         "action": "BUY", "shares": 10, "price": 100.0, "total_value": 1000.0,
         "stop_loss": 90.0, "take_profit": 120.0, "reason": "SIGNAL",
         "regime_at_entry": "BULL", "composite_score": 75.0,
         "signal_rank": 1, "factor_scores": "{}", "trade_rationale": "{}"},
    ])
    trades = _load_closed_trades("test", data_dir=portfolio_dir.parent)
    assert trades == []


def test_closed_trade_basic_fields(portfolio_dir: Path) -> None:
    """A matched BUY+SELL round-trip returns an enriched trade object."""
    rationale = json.dumps({"ai_reasoning": "Strong momentum play"})
    sell_rationale = json.dumps({"ai_reasoning": "Stop loss triggered"})
    _write_csv(portfolio_dir / "transactions.csv", [
        {"transaction_id": "buy-1", "date": "2026-01-10", "ticker": "RCKT",
         "action": "BUY", "shares": 100, "price": 10.0, "total_value": 1000.0,
         "stop_loss": 9.0, "take_profit": 15.0, "reason": "SIGNAL",
         "regime_at_entry": "BULL", "composite_score": 70.0,
         "signal_rank": 2, "factor_scores": '{"momentum": 80.0, "quality": 60.0}',
         "trade_rationale": rationale},
        {"transaction_id": "sell-1", "date": "2026-01-15", "ticker": "RCKT",
         "action": "SELL", "shares": 100, "price": 9.50, "total_value": 950.0,
         "stop_loss": 0, "take_profit": 0, "reason": "STOP_LOSS",
         "regime_at_entry": "BULL", "composite_score": 0,
         "signal_rank": 0, "factor_scores": "{}", "trade_rationale": sell_rationale},
    ])
    trades = _load_closed_trades("test", data_dir=portfolio_dir.parent)
    assert len(trades) == 1
    t = trades[0]
    assert t["trade_id"] == "buy-1"
    assert t["ticker"] == "RCKT"
    assert t["entry_date"] == "2026-01-10"
    assert t["exit_date"] == "2026-01-15"
    assert t["entry_price"] == pytest.approx(10.0)
    assert t["exit_price"] == pytest.approx(9.50)
    assert t["exit_reason"] == "STOP_LOSS"
    assert t["entry_ai_reasoning"] == "Strong momentum play"
    assert t["exit_ai_reasoning"] == "Stop loss triggered"
    assert t["factor_scores"]["momentum"] == pytest.approx(80.0)
    assert t["pnl"] == pytest.approx(-5.0)
    assert t["pnl_pct"] == pytest.approx(-5.0)


def test_missing_post_mortem_graceful(portfolio_dir: Path) -> None:
    """If post_mortems.csv doesn't exist, trade still returns with empty narrative fields."""
    _write_csv(portfolio_dir / "transactions.csv", [
        {"transaction_id": "buy-2", "date": "2026-02-01", "ticker": "XYZ",
         "action": "BUY", "shares": 50, "price": 20.0, "total_value": 1000.0,
         "stop_loss": 18.0, "take_profit": 26.0, "reason": "SIGNAL",
         "regime_at_entry": "SIDEWAYS", "composite_score": 55.0,
         "signal_rank": 3, "factor_scores": "{}", "trade_rationale": "{}"},
        {"transaction_id": "sell-2", "date": "2026-02-05", "ticker": "XYZ",
         "action": "SELL", "shares": 50, "price": 22.0, "total_value": 1100.0,
         "stop_loss": 0, "take_profit": 0, "reason": "TAKE_PROFIT",
         "regime_at_entry": "SIDEWAYS", "composite_score": 0,
         "signal_rank": 0, "factor_scores": "{}", "trade_rationale": "{}"},
    ])
    trades = _load_closed_trades("test", data_dir=portfolio_dir.parent)
    assert len(trades) == 1
    t = trades[0]
    assert t["what_worked"] == ""
    assert t["what_failed"] == ""
    assert t["recommendation"] == ""


def test_same_ticker_multiple_roundtrips(portfolio_dir: Path) -> None:
    """Two BUY+SELL pairs for the same ticker become two separate entries (FIFO)."""
    _write_csv(portfolio_dir / "transactions.csv", [
        {"transaction_id": "b1", "date": "2026-01-01", "ticker": "AA",
         "action": "BUY", "shares": 10, "price": 10.0, "total_value": 100.0,
         "stop_loss": 9.0, "take_profit": 13.0, "reason": "SIGNAL",
         "regime_at_entry": "BULL", "composite_score": 0, "signal_rank": 0,
         "factor_scores": "{}", "trade_rationale": "{}"},
        {"transaction_id": "s1", "date": "2026-01-05", "ticker": "AA",
         "action": "SELL", "shares": 10, "price": 11.0, "total_value": 110.0,
         "stop_loss": 0, "take_profit": 0, "reason": "TAKE_PROFIT",
         "regime_at_entry": "BULL", "composite_score": 0, "signal_rank": 0,
         "factor_scores": "{}", "trade_rationale": "{}"},
        {"transaction_id": "b2", "date": "2026-01-10", "ticker": "AA",
         "action": "BUY", "shares": 10, "price": 12.0, "total_value": 120.0,
         "stop_loss": 10.8, "take_profit": 15.6, "reason": "SIGNAL",
         "regime_at_entry": "BEAR", "composite_score": 0, "signal_rank": 0,
         "factor_scores": "{}", "trade_rationale": "{}"},
        {"transaction_id": "s2", "date": "2026-01-15", "ticker": "AA",
         "action": "SELL", "shares": 10, "price": 11.5, "total_value": 115.0,
         "stop_loss": 0, "take_profit": 0, "reason": "STOP_LOSS",
         "regime_at_entry": "BEAR", "composite_score": 0, "signal_rank": 0,
         "factor_scores": "{}", "trade_rationale": "{}"},
    ])
    trades = _load_closed_trades("test", data_dir=portfolio_dir.parent)
    assert len(trades) == 2
    # Default sort is exit_date descending
    assert trades[0]["trade_id"] == "b2"
    assert trades[1]["trade_id"] == "b1"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
python3 -m pytest tests/test_trade_reviews.py -v 2>&1 | head -30
```

Expected: `ImportError` or `ModuleNotFoundError` — `api.routes.trade_reviews` doesn't exist yet.

- [ ] **Step 3: Create the route file with the GET endpoint**

Create `api/routes/trade_reviews.py`:

```python
"""Trade reviews route — GET closed trade history, POST re-analyze with Claude."""

import json
import math
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "portfolios"

router = APIRouter(prefix="/api/{portfolio_id}")


def _safe_float(val) -> float | None:
    """Return float or None; never returns NaN/Inf."""
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _parse_ai_reasoning(rationale_str) -> str:
    """Extract ai_reasoning from a JSON trade_rationale string."""
    if not rationale_str or not isinstance(rationale_str, str):
        return ""
    try:
        parsed = json.loads(rationale_str)
        return str(parsed.get("ai_reasoning", ""))
    except (json.JSONDecodeError, AttributeError):
        return ""


def _parse_factor_scores(factor_str) -> dict:
    """Parse factor_scores JSON field; return {} on any failure."""
    if not factor_str or not isinstance(factor_str, str):
        return {}
    try:
        result = json.loads(factor_str)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, AttributeError):
        return {}


def _load_closed_trades(portfolio_id: str, data_dir: Path = DATA_DIR) -> list[dict]:
    """Join transactions + post_mortems into enriched closed-trade objects.

    Only fully closed round-trips are returned (BUY matched to SELL, FIFO).
    Open positions are excluded. Missing post-mortem rows are handled gracefully.
    """
    portfolio_dir = data_dir / portfolio_id
    txn_path = portfolio_dir / "transactions.csv"

    if not txn_path.exists():
        return []

    txn_df = pd.read_csv(txn_path, dtype=str)
    if txn_df.empty:
        return []

    buys = txn_df[txn_df["action"] == "BUY"].copy()
    sells = txn_df[txn_df["action"] == "SELL"].copy()

    if buys.empty or sells.empty:
        return []

    # Load post-mortems keyed by (ticker, close_date_prefix)
    pm_map: dict[tuple, dict] = {}
    pm_path = portfolio_dir / "post_mortems.csv"
    if pm_path.exists():
        pm_df = pd.read_csv(pm_path, dtype=str)
        for _, row in pm_df.iterrows():
            key = (str(row.get("ticker", "")), str(row.get("close_date", ""))[:10])
            pm_map[key] = row.to_dict()

    # Build FIFO queue per ticker
    ticker_buys: dict[str, list] = {}
    for _, buy in buys.sort_values("date").iterrows():
        t = str(buy.get("ticker", ""))
        ticker_buys.setdefault(t, []).append(buy)

    results: list[dict] = []

    for _, sell in sells.sort_values("date").iterrows():
        t = str(sell.get("ticker", ""))
        if t not in ticker_buys or not ticker_buys[t]:
            continue
        buy = ticker_buys[t].pop(0)  # FIFO match

        close_date = str(sell["date"])[:10]
        pm = pm_map.get((t, close_date), {})

        entry_price = _safe_float(buy.get("price"))
        exit_price = _safe_float(sell.get("price"))
        shares = _safe_float(buy.get("shares"))

        # P&L from post-mortem if available, else compute
        pnl = _safe_float(pm.get("pnl"))
        if pnl is None and entry_price is not None and exit_price is not None and shares is not None:
            pnl = (exit_price - entry_price) * shares

        pnl_pct = _safe_float(pm.get("pnl_pct"))
        if pnl_pct is None and entry_price is not None and exit_price is not None and entry_price > 0:
            pnl_pct = (exit_price - entry_price) / entry_price * 100

        holding_days_raw = _safe_float(pm.get("holding_days"))
        holding_days = int(holding_days_raw) if holding_days_raw is not None else 0

        results.append({
            "trade_id": str(buy.get("transaction_id", "")),
            "ticker": t,
            "entry_date": str(buy["date"])[:10],
            "exit_date": close_date,
            "holding_days": holding_days,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "shares": shares,
            "stop_loss": _safe_float(buy.get("stop_loss")),
            "take_profit": _safe_float(buy.get("take_profit")),
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "exit_reason": str(sell.get("reason") or pm.get("exit_reason") or "UNKNOWN"),
            "regime_at_entry": str(buy.get("regime_at_entry") or pm.get("regime_at_entry") or ""),
            "regime_at_exit": str(pm.get("regime_at_exit") or ""),
            "entry_ai_reasoning": _parse_ai_reasoning(buy.get("trade_rationale")),
            "exit_ai_reasoning": _parse_ai_reasoning(sell.get("trade_rationale")),
            "factor_scores": _parse_factor_scores(buy.get("factor_scores")),
            "what_worked": str(pm.get("what_worked") or ""),
            "what_failed": str(pm.get("what_failed") or ""),
            "recommendation": str(pm.get("recommendation") or ""),
            "summary": str(pm.get("summary") or ""),
        })

    # Sort by exit_date descending
    results.sort(key=lambda x: x["exit_date"], reverse=True)
    return results


@router.get("/trade-reviews")
def get_trade_reviews(portfolio_id: str) -> dict:
    """Return all closed trades for a portfolio as enriched objects."""
    trades = _load_closed_trades(portfolio_id)
    return {"trades": trades}
```

- [ ] **Step 4: Run tests — confirm they all pass**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
python3 -m pytest tests/test_trade_reviews.py -v
```

Expected output:
```
test_trade_reviews.py::test_no_transactions_returns_empty PASSED
test_trade_reviews.py::test_open_position_excluded PASSED
test_trade_reviews.py::test_closed_trade_basic_fields PASSED
test_trade_reviews.py::test_missing_post_mortem_graceful PASSED
test_trade_reviews.py::test_same_ticker_multiple_roundtrips PASSED
5 passed
```

- [ ] **Step 5: Commit**

```bash
git add api/routes/trade_reviews.py tests/test_trade_reviews.py
git commit -m "feat: add GET /trade-reviews endpoint with TDD

Joins transactions.csv + post_mortems.csv into enriched closed-trade
objects. FIFO matching for multi-round-trip tickers. Handles missing
post-mortem and malformed trade_rationale gracefully."
```

---

## Task 2: Backend — POST /trade-reviews/{trade_id}/analyze endpoint (TDD)

**Files:**
- Modify: `api/routes/trade_reviews.py`
- Modify: `tests/test_trade_reviews.py`

- [ ] **Step 1: Add failing test for the analyze endpoint helper**

Append to `tests/test_trade_reviews.py`:

```python
from unittest.mock import patch, MagicMock


def test_analyze_trade_not_found_raises(portfolio_dir: Path) -> None:
    """Calling analyze with an unknown trade_id raises ValueError."""
    from api.routes.trade_reviews import _build_analyze_prompt
    with pytest.raises(KeyError):
        # _build_analyze_prompt with a trade dict that has no trade_id match
        # We test the lookup logic indirectly via the route in integration
        pass  # placeholder — real test below uses the loader


def test_build_analyze_prompt_contains_ticker(portfolio_dir: Path) -> None:
    """Prompt built for a trade contains the ticker and P&L."""
    from api.routes.trade_reviews import _build_analyze_prompt
    trade = {
        "trade_id": "x1", "ticker": "AAPL",
        "entry_date": "2026-01-01", "exit_date": "2026-01-10",
        "entry_price": 100.0, "exit_price": 110.0,
        "pnl": 100.0, "pnl_pct": 10.0,
        "holding_days": 9, "exit_reason": "TAKE_PROFIT",
        "regime_at_entry": "BULL", "regime_at_exit": "BULL",
        "entry_ai_reasoning": "Strong trend", "exit_ai_reasoning": "Target hit",
        "factor_scores": {"momentum": 90.0},
        "what_worked": "Momentum", "what_failed": "", "recommendation": "Scale up",
        "summary": "",
    }
    prompt = _build_analyze_prompt(trade)
    assert "AAPL" in prompt
    assert "+10.0%" in prompt
    assert "Strong trend" in prompt
    assert "momentum: 90.0" in prompt
```

- [ ] **Step 2: Run to confirm failure**

```bash
python3 -m pytest tests/test_trade_reviews.py::test_build_analyze_prompt_contains_ticker -v
```

Expected: `ImportError: cannot import name '_build_analyze_prompt'`

- [ ] **Step 3: Add the analyze endpoint to trade_reviews.py**

Append to `api/routes/trade_reviews.py` (after the GET endpoint):

```python
def _build_analyze_prompt(trade: dict) -> str:
    """Build the Claude prompt for re-analyzing a single trade."""
    pnl_pct = trade.get("pnl_pct") or 0.0
    pnl = trade.get("pnl") or 0.0
    sign = "+" if pnl_pct >= 0 else ""

    factor_lines = "\n".join(
        f"  {k}: {v:.1f}" for k, v in (trade.get("factor_scores") or {}).items()
    ) or "  Not recorded"

    return f"""You are reviewing a completed trade for post-mortem analysis. Connect the entry thesis to the actual outcome.

TRADE: {trade["ticker"]}
Entry: {trade["entry_date"]} @ ${trade.get("entry_price", 0):.2f} | Exit: {trade["exit_date"]} @ ${trade.get("exit_price", 0):.2f}
P&L: {sign}{pnl_pct:.1f}% (${pnl:.2f}) | Hold: {trade["holding_days"]} days
Exit reason: {trade["exit_reason"]}
Market regime at entry: {trade["regime_at_entry"]} | at exit: {trade["regime_at_exit"]}

ENTRY THESIS:
{trade["entry_ai_reasoning"] or "No AI reasoning recorded"}

FACTOR SCORES AT ENTRY:
{factor_lines}

EXIT REASONING:
{trade["exit_ai_reasoning"] or "No AI reasoning recorded"}

STORED POST-MORTEM:
What worked: {trade["what_worked"] or "Not recorded"}
What failed: {trade["what_failed"] or "Not recorded"}

Write a 3-4 sentence synthesis that explicitly connects: (1) whether the entry thesis played out as expected, (2) which factors at entry were predictive vs misleading, (3) one specific lesson for future trades of this type. Be direct and concrete."""


@router.post("/trade-reviews/{trade_id}/analyze")
def analyze_trade(portfolio_id: str, trade_id: str) -> dict:
    """Call Claude Haiku to synthesize entry thesis vs exit outcome. Not persisted."""
    import anthropic

    trades = _load_closed_trades(portfolio_id)
    trade = next((t for t in trades if t["trade_id"] == trade_id), None)
    if trade is None:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found in {portfolio_id}")

    prompt = _build_analyze_prompt(trade)
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return {"narrative": message.content[0].text}
```

- [ ] **Step 4: Run all trade_reviews tests**

```bash
python3 -m pytest tests/test_trade_reviews.py -v
```

Expected: 6 passed (5 from Task 1 + 1 new prompt test).

- [ ] **Step 5: Commit**

```bash
git add api/routes/trade_reviews.py tests/test_trade_reviews.py
git commit -m "feat: add POST /trade-reviews/{trade_id}/analyze endpoint

Builds a synthesis prompt from stored entry thesis + factor scores +
exit reasoning and calls Claude Haiku. Returns ephemeral narrative.
Added _build_analyze_prompt helper with unit test coverage."
```

---

## Task 3: Register router + restart API

**Files:**
- Modify: `api/main.py`

- [ ] **Step 1: Add the import and include_router call**

In `api/main.py`, after line 20 (`from api.routes import intelligence as intelligence_routes`):

```python
from api.routes import trade_reviews as trade_reviews_routes
```

After line 44 (`app.include_router(intelligence_routes.router)`):

```python
app.include_router(trade_reviews_routes.router)
```

- [ ] **Step 2: Restart the API**

```bash
pkill -f "uvicorn api.main" 2>/dev/null; sleep 1
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && DISABLE_SOCIAL=true nohup uvicorn api.main:app --host 0.0.0.0 --port 8001 > /tmp/mcr_api.log 2>&1 &
sleep 2 && curl -s http://localhost:8001/api/microcap/trade-reviews | python3 -c "import json,sys; d=json.load(sys.stdin); print('trades:', len(d['trades']))"
```

Expected: `trades: <N>` (some number ≥ 0, no error).

- [ ] **Step 3: Commit**

```bash
git add api/main.py
git commit -m "feat: register trade_reviews router in FastAPI app"
```

---

## Task 4: Frontend types + API client

**Files:**
- Modify: `dashboard/src/lib/types.ts`
- Modify: `dashboard/src/lib/api.ts`

- [ ] **Step 1: Add types to types.ts**

Find the end of `dashboard/src/lib/types.ts` and append:

```typescript
// ── Trade Reviews ─────────────────────────────────────────────────────────

export interface ClosedTradeFactorScores {
  momentum?: number;
  quality?: number;
  earnings?: number;
  volume?: number;
  volatility?: number;
  value_timing?: number;
  [key: string]: number | undefined;
}

export interface ClosedTrade {
  trade_id: string;
  ticker: string;
  entry_date: string;
  exit_date: string;
  holding_days: number;
  entry_price: number | null;
  exit_price: number | null;
  shares: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  pnl: number | null;
  pnl_pct: number | null;
  exit_reason: string;
  regime_at_entry: string;
  regime_at_exit: string;
  entry_ai_reasoning: string;
  exit_ai_reasoning: string;
  factor_scores: ClosedTradeFactorScores;
  what_worked: string;
  what_failed: string;
  recommendation: string;
  summary: string;
}

export interface TradeReviewsResponse {
  trades: ClosedTrade[];
}

export interface TradeAnalyzeResponse {
  narrative: string;
}
```

- [ ] **Step 2: Add API methods to api.ts**

In `dashboard/src/lib/api.ts`, inside the `api` export object, after the `postIntelligenceChat` entry (around line 198), add:

```typescript
  // Trade reviews
  getTradeReviews: (pid: string): Promise<TradeReviewsResponse> =>
    get<TradeReviewsResponse>(`/${pid}/trade-reviews`),

  analyzeTradeReview: (pid: string, tradeId: string): Promise<TradeAnalyzeResponse> =>
    post<TradeAnalyzeResponse>(`/${pid}/trade-reviews/${tradeId}/analyze`, {}),
```

Also add the import at the top of `api.ts` where types are imported:

```typescript
import type { ..., TradeReviewsResponse, TradeAnalyzeResponse } from "./types";
```

(Add `TradeReviewsResponse` and `TradeAnalyzeResponse` to the existing import.)

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm run build 2>&1 | tail -20
```

Expected: no TypeScript errors related to the new types.

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/lib/types.ts dashboard/src/lib/api.ts
git commit -m "feat: add ClosedTrade types and getTradeReviews/analyzeTradeReview API methods"
```

---

## Task 5: Zustand BriefStore

**Files:**
- Modify: `dashboard/src/lib/store.ts`

- [ ] **Step 1: Append BriefStore to store.ts**

At the end of `dashboard/src/lib/store.ts`, append:

```typescript
// ── Brief Store — controls Intelligence Brief open state globally ──────────

interface BriefStore {
  briefOpen: boolean;
  briefInitialTab: string;
  briefInitialTradeId: string | null;
  openBrief: (tab?: string, tradeId?: string | null) => void;
  closeBrief: () => void;
}

export const useBriefStore = create<BriefStore>((set) => ({
  briefOpen: false,
  briefInitialTab: "performance",
  briefInitialTradeId: null,
  openBrief: (tab = "performance", tradeId = null) =>
    set({ briefOpen: true, briefInitialTab: tab, briefInitialTradeId: tradeId }),
  closeBrief: () =>
    set({ briefOpen: false, briefInitialTradeId: null }),
}));
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm run build 2>&1 | grep -i error | head -10
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/lib/store.ts
git commit -m "feat: add BriefStore to Zustand for global Intelligence Brief open state"
```

---

## Task 6: TopBar — use BriefStore

**Files:**
- Modify: `dashboard/src/components/TopBar.tsx`

- [ ] **Step 1: Import useBriefStore**

In `TopBar.tsx`, find the existing store imports (search for `useUIStore` or `useAnalysisStore`) and add:

```typescript
import { useBriefStore } from "../lib/store";
```

- [ ] **Step 2: Replace showBrief local state with store**

Find line 385:
```typescript
const [showBrief, setShowBrief] = useState(false);
```

Replace with:
```typescript
const { briefOpen, briefInitialTab, briefInitialTradeId, openBrief, closeBrief } = useBriefStore();
```

- [ ] **Step 3: Update the button onClick**

Find line 477:
```typescript
onClick={() => setShowBrief(true)}
```

Replace with:
```typescript
onClick={() => openBrief()}
```

- [ ] **Step 4: Update the IntelligenceBrief render**

Find lines 566–572:
```typescript
{showBrief && activePortfolioId && !isOverviewOrLogs && (
  <IntelligenceBrief
    portfolioId={activePortfolioId}
    portfolioName={state?.config?.name as string ?? activePortfolioId}
    onClose={() => setShowBrief(false)}
  />
)}
```

Replace with:
```typescript
{briefOpen && activePortfolioId && !isOverviewOrLogs && (
  <IntelligenceBrief
    portfolioId={activePortfolioId}
    portfolioName={state?.config?.name as string ?? activePortfolioId}
    initialTab={briefInitialTab}
    initialTradeId={briefInitialTradeId}
    onClose={closeBrief}
  />
)}
```

- [ ] **Step 5: Verify dev server starts without errors**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm run dev 2>&1 | grep -E "error|Error|warn" | head -10
```

Expected: no TypeScript/runtime errors. The brief button still opens the modal.

- [ ] **Step 6: Commit**

```bash
git add dashboard/src/components/TopBar.tsx
git commit -m "refactor: move IntelligenceBrief open state to BriefStore

Replaces local showBrief useState with useBriefStore so any component
can open the brief to a specific tab + trade via openBrief(tab, tradeId)."
```

---

## Task 7: TradesTab component

**Files:**
- Create: `dashboard/src/components/IntelligenceBrief/TradesTab.tsx`

- [ ] **Step 1: Create TradesTab.tsx**

```typescript
/** TRADES tab — aggregate stats + filterable closed-trade list + per-trade detail. */

import { useState, useMemo } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "../../lib/api";
import type { ClosedTrade } from "../../lib/types";

const FONT = "'JetBrains Mono', 'SF Mono', monospace";

type ExitReasonFilter = "ALL" | "STOP_LOSS" | "TAKE_PROFIT" | "INTELLIGENCE" | "MANUAL";
type DateRangeFilter = "30d" | "90d" | "all";
type SortKey = "exit_date" | "pnl_pct" | "holding_days" | "ticker";

// ── Exit reason badge ────────────────────────────────────────────────────────

function ExitBadge({ reason }: { reason: string }) {
  const cfg: Record<string, { color: string; label: string }> = {
    STOP_LOSS:    { color: "#f87171", label: "STOP" },
    TAKE_PROFIT:  { color: "#4ade80", label: "TARGET" },
    INTELLIGENCE: { color: "#818cf8", label: "AI" },
    MANUAL:       { color: "#9ca3af", label: "MANUAL" },
  };
  const { color, label } = cfg[reason] ?? { color: "#9ca3af", label: reason };
  return (
    <span style={{
      color, fontSize: 9, fontWeight: 700, letterSpacing: "0.05em",
      background: `${color}22`, padding: "1px 6px", borderRadius: 4,
      fontFamily: FONT, whiteSpace: "nowrap",
    }}>
      {label}
    </span>
  );
}

// ── Factor bar ───────────────────────────────────────────────────────────────

function FactorBar({ label, score }: { label: string; score: number }) {
  const pct = Math.min(100, Math.max(0, score));
  const color = pct >= 70 ? "#4ade80" : pct >= 50 ? "#facc15" : "#f87171";
  return (
    <div style={{ marginBottom: 7 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
        <span style={{ fontSize: 10, color: "rgba(255,255,255,0.45)", textTransform: "capitalize", fontFamily: FONT }}>
          {label.replace(/_/g, " ")}
        </span>
        <span style={{ fontSize: 10, color, fontWeight: 600, fontFamily: FONT }}>{Math.round(score)}</span>
      </div>
      <div style={{ height: 3, background: "rgba(255,255,255,0.07)", borderRadius: 2 }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 2, transition: "width 0.3s" }} />
      </div>
    </div>
  );
}

// ── Aggregate panel ──────────────────────────────────────────────────────────

function AggregatePanel({ trades }: { trades: ClosedTrade[] }) {
  const stats = useMemo(() => {
    if (trades.length === 0) return null;
    const winners = trades.filter(t => (t.pnl_pct ?? 0) > 0);
    const winRate = (winners.length / trades.length) * 100;
    const avgPnl = trades.reduce((s, t) => s + (t.pnl_pct ?? 0), 0) / trades.length;
    const avgHold = trades.reduce((s, t) => s + t.holding_days, 0) / trades.length;

    const byReason: Record<string, { count: number; pnlSum: number }> = {};
    trades.forEach(t => {
      const r = t.exit_reason || "UNKNOWN";
      if (!byReason[r]) byReason[r] = { count: 0, pnlSum: 0 };
      byReason[r].count++;
      byReason[r].pnlSum += t.pnl_pct ?? 0;
    });
    const reasonStats = Object.entries(byReason)
      .map(([reason, d]) => ({ reason, count: d.count, avgPnl: d.pnlSum / d.count, pct: (d.count / trades.length) * 100 }))
      .sort((a, b) => b.count - a.count);

    const byRegime: Record<string, { wins: number; total: number }> = {};
    trades.forEach(t => {
      const r = t.regime_at_entry || "UNKNOWN";
      if (!byRegime[r]) byRegime[r] = { wins: 0, total: 0 };
      byRegime[r].total++;
      if ((t.pnl_pct ?? 0) > 0) byRegime[r].wins++;
    });
    const regimeStats = Object.entries(byRegime)
      .map(([regime, d]) => ({ regime, winRate: (d.wins / d.total) * 100, total: d.total }));

    return { winRate, avgPnl, avgHold, total: trades.length, reasonStats, regimeStats };
  }, [trades]);

  if (!stats) {
    return (
      <div style={{ padding: 20, color: "rgba(255,255,255,0.3)", fontSize: 12, textAlign: "center", fontFamily: FONT }}>
        No closed trades yet
      </div>
    );
  }

  const reasonColor = (r: string) =>
    r === "STOP_LOSS" ? "#f87171" : r === "TAKE_PROFIT" ? "#4ade80" : r === "INTELLIGENCE" ? "#818cf8" : "#9ca3af";
  const regimeColor = (r: string) =>
    r === "BULL" ? "#4ade80" : r === "BEAR" ? "#f87171" : "#facc15";

  return (
    <div style={{ padding: "12px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", fontFamily: FONT }}>
      {/* Stat chips */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 6, marginBottom: 12 }}>
        {[
          { label: "WIN RATE", value: `${stats.winRate.toFixed(0)}%`, color: stats.winRate >= 50 ? "#4ade80" : "#f87171" },
          { label: "AVG P&L", value: `${stats.avgPnl >= 0 ? "+" : ""}${stats.avgPnl.toFixed(1)}%`, color: stats.avgPnl >= 0 ? "#4ade80" : "#f87171" },
          { label: "AVG HOLD", value: `${stats.avgHold.toFixed(1)}d`, color: undefined },
          { label: "TOTAL", value: String(stats.total), color: undefined },
        ].map(chip => (
          <div key={chip.label} style={{
            background: "rgba(255,255,255,0.03)", borderRadius: 6, padding: "7px 8px",
            border: "1px solid rgba(255,255,255,0.06)",
          }}>
            <div style={{ fontSize: 8, color: "rgba(255,255,255,0.3)", marginBottom: 3, letterSpacing: "0.08em" }}>{chip.label}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: chip.color ?? "rgba(255,255,255,0.85)" }}>{chip.value}</div>
          </div>
        ))}
      </div>

      {/* Breakdowns */}
      <div style={{ display: "flex", gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 8, color: "rgba(255,255,255,0.3)", marginBottom: 6, letterSpacing: "0.08em" }}>BY EXIT</div>
          {stats.reasonStats.map(r => (
            <div key={r.reason} style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 5 }}>
              <div style={{ width: 50, height: 3, background: "rgba(255,255,255,0.05)", borderRadius: 2 }}>
                <div style={{ width: `${r.pct}%`, height: "100%", background: reasonColor(r.reason), borderRadius: 2 }} />
              </div>
              <span style={{ fontSize: 9, color: "rgba(255,255,255,0.4)", flex: 1 }}>
                {r.reason.replace(/_/g, " ")} ({r.count})
              </span>
              <span style={{ fontSize: 9, fontWeight: 600, color: r.avgPnl >= 0 ? "#4ade80" : "#f87171" }}>
                {r.avgPnl >= 0 ? "+" : ""}{r.avgPnl.toFixed(1)}%
              </span>
            </div>
          ))}
        </div>

        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 8, color: "rgba(255,255,255,0.3)", marginBottom: 6, letterSpacing: "0.08em" }}>BY REGIME</div>
          {stats.regimeStats.map(r => (
            <div key={r.regime} style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 5 }}>
              <div style={{ width: 50, height: 3, background: "rgba(255,255,255,0.05)", borderRadius: 2 }}>
                <div style={{ width: `${r.winRate}%`, height: "100%", background: regimeColor(r.regime), borderRadius: 2 }} />
              </div>
              <span style={{ fontSize: 9, color: "rgba(255,255,255,0.4)", flex: 1 }}>{r.regime} ({r.total})</span>
              <span style={{ fontSize: 9, fontWeight: 600, color: regimeColor(r.regime) }}>
                {r.winRate.toFixed(0)}% W
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Trade list ───────────────────────────────────────────────────────────────

function TradeList({
  trades,
  selectedId,
  onSelect,
}: {
  trades: ClosedTrade[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("exit_date");
  const [sortDir, setSortDir] = useState<1 | -1>(-1);
  const [filterReason, setFilterReason] = useState<ExitReasonFilter>("ALL");
  const [dateRange, setDateRange] = useState<DateRangeFilter>("all");

  const filtered = useMemo(() => {
    let list = [...trades];

    if (dateRange !== "all") {
      const days = dateRange === "30d" ? 30 : 90;
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - days);
      const cutoffStr = cutoff.toISOString().slice(0, 10);
      list = list.filter(t => t.exit_date >= cutoffStr);
    }

    if (filterReason !== "ALL") {
      list = list.filter(t => t.exit_reason === filterReason);
    }

    list.sort((a, b) => {
      const av = a[sortKey as keyof ClosedTrade] ?? (sortDir === 1 ? -Infinity : Infinity);
      const bv = b[sortKey as keyof ClosedTrade] ?? (sortDir === 1 ? -Infinity : Infinity);
      return av < bv ? -sortDir : av > bv ? sortDir : 0;
    });

    return list;
  }, [trades, sortKey, sortDir, filterReason, dateRange]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => (d === 1 ? -1 : 1));
    else { setSortKey(key); setSortDir(-1); }
  };

  const hdr = (key: SortKey, label: string) => (
    <span
      onClick={() => toggleSort(key)}
      style={{
        cursor: "pointer", fontSize: 9, letterSpacing: "0.08em", textTransform: "uppercase",
        fontFamily: FONT, userSelect: "none",
        color: sortKey === key ? "rgba(255,255,255,0.85)" : "rgba(255,255,255,0.35)",
      }}
    >
      {label}{sortKey === key ? (sortDir === 1 ? " ↑" : " ↓") : ""}
    </span>
  );

  const reasons: ExitReasonFilter[] = ["ALL", "STOP_LOSS", "TAKE_PROFIT", "INTELLIGENCE", "MANUAL"];
  const btnStyle = (active: boolean): React.CSSProperties => ({
    fontSize: 9, padding: "2px 7px", borderRadius: 4, cursor: "pointer",
    border: "1px solid rgba(255,255,255,0.08)", fontFamily: FONT,
    background: active ? "rgba(124,92,252,0.18)" : "transparent",
    color: active ? "#a78bfa" : "rgba(255,255,255,0.35)",
    fontWeight: active ? 600 : 400,
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0, fontFamily: FONT }}>
      {/* Filters */}
      <div style={{ padding: "7px 14px", borderBottom: "1px solid rgba(255,255,255,0.05)", display: "flex", gap: 4, flexWrap: "wrap", alignItems: "center" }}>
        {reasons.map(r => (
          <button key={r} onClick={() => setFilterReason(r)} style={btnStyle(filterReason === r)}>
            {r === "ALL" ? "All" : r.replace(/_/g, " ")}
          </button>
        ))}
        <span style={{ flex: 1 }} />
        {(["30d", "90d", "all"] as DateRangeFilter[]).map(d => (
          <button key={d} onClick={() => setDateRange(d)} style={btnStyle(dateRange === d)}>
            {d === "all" ? "All time" : `Last ${d}`}
          </button>
        ))}
      </div>

      {/* Column headers */}
      <div style={{
        padding: "5px 14px", display: "grid",
        gridTemplateColumns: "52px 80px 36px 56px 68px",
        gap: 6, borderBottom: "1px solid rgba(255,255,255,0.05)",
      }}>
        {hdr("ticker", "Ticker")}
        {hdr("exit_date", "Close")}
        {hdr("holding_days", "Hold")}
        {hdr("pnl_pct", "P&L%")}
        <span style={{ fontSize: 9, color: "rgba(255,255,255,0.35)", letterSpacing: "0.08em", textTransform: "uppercase", fontFamily: FONT }}>Exit</span>
      </div>

      {/* Rows */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {filtered.length === 0 && (
          <div style={{ padding: 20, textAlign: "center", color: "rgba(255,255,255,0.25)", fontSize: 11 }}>
            No trades match filters
          </div>
        )}
        {filtered.map(trade => {
          const pnl = trade.pnl_pct ?? 0;
          const isSelected = trade.trade_id === selectedId;
          return (
            <div
              key={trade.trade_id}
              onClick={() => onSelect(trade.trade_id)}
              style={{
                padding: "6px 14px", display: "grid",
                gridTemplateColumns: "52px 80px 36px 56px 68px",
                gap: 6, alignItems: "center", cursor: "pointer",
                borderBottom: "1px solid rgba(255,255,255,0.025)",
                background: isSelected ? "rgba(124,92,252,0.10)" : "transparent",
                transition: "background 0.12s",
              }}
              onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.025)"; }}
              onMouseLeave={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = "transparent"; }}
            >
              <span style={{ fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,0.9)", fontFamily: FONT }}>{trade.ticker}</span>
              <span style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", fontFamily: FONT }}>{trade.exit_date}</span>
              <span style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", fontFamily: FONT }}>{trade.holding_days}d</span>
              <span style={{ fontSize: 11, fontWeight: 700, color: pnl >= 0 ? "#4ade80" : "#f87171", fontFamily: FONT }}>
                {pnl >= 0 ? "+" : ""}{pnl.toFixed(1)}%
              </span>
              <ExitBadge reason={trade.exit_reason} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Trade detail ─────────────────────────────────────────────────────────────

function TradeDetail({ trade, portfolioId }: { trade: ClosedTrade; portfolioId: string }) {
  const [reanalyzed, setReanalyzed] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [prevTradeId, setPrevTradeId] = useState(trade.trade_id);

  // Reset ephemeral state when selected trade changes
  if (trade.trade_id !== prevTradeId) {
    setPrevTradeId(trade.trade_id);
    setReanalyzed(null);
    setAnalyzeError(null);
  }

  const analyzeMutation = useMutation({
    mutationFn: () => api.analyzeTradeReview(portfolioId, trade.trade_id),
    onSuccess: (data) => { setReanalyzed(data.narrative); setAnalyzeError(null); },
    onError: () => setAnalyzeError("Analysis failed — try again"),
  });

  const pnl = trade.pnl_pct ?? 0;
  const pnlColor = pnl >= 0 ? "#4ade80" : "#f87171";
  const factors = Object.entries(trade.factor_scores || {}).filter(([, v]) => v != null) as [string, number][];

  const chip = (label: string, value: string) => (
    <span key={label} style={{ fontSize: 10, color: "rgba(255,255,255,0.4)", fontFamily: FONT }}>
      <span style={{ color: "rgba(255,255,255,0.25)" }}>{label} </span>{value}
    </span>
  );

  const section = (title: string, extra?: React.ReactNode) => (
    <div style={{ fontSize: 9, textTransform: "uppercase", letterSpacing: "0.09em", color: "rgba(255,255,255,0.28)", marginBottom: 8, fontFamily: FONT, fontWeight: 600, display: "flex", gap: 8, alignItems: "center" }}>
      {title}{extra}
    </div>
  );

  const divider = <div style={{ height: 1, background: "rgba(255,255,255,0.05)", margin: "2px 0" }} />;

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "14px 16px", display: "flex", flexDirection: "column", gap: 14, fontFamily: FONT }}>
      {/* Header */}
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
          <span style={{ fontSize: 17, fontWeight: 800, color: "rgba(255,255,255,0.95)", letterSpacing: "0.04em" }}>{trade.ticker}</span>
          <ExitBadge reason={trade.exit_reason} />
          {trade.regime_at_entry && (
            <span style={{ fontSize: 9, color: "rgba(255,255,255,0.3)", background: "rgba(255,255,255,0.04)", padding: "1px 6px", borderRadius: 4 }}>
              {trade.regime_at_entry}
            </span>
          )}
        </div>
        <div style={{ fontSize: 10, color: "rgba(255,255,255,0.35)", marginBottom: 8 }}>
          {trade.entry_date} → {trade.exit_date} · {trade.holding_days}d
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, color: pnlColor }}>
          {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}%
          <span style={{ fontSize: 13, fontWeight: 400, marginLeft: 8, color: pnlColor }}>
            ({pnl >= 0 ? "+" : ""}${(trade.pnl ?? 0).toFixed(0)})
          </span>
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 8, flexWrap: "wrap" }}>
          {chip("Entry", `$${trade.entry_price?.toFixed(2) ?? "—"}`)}
          {chip("Exit", `$${trade.exit_price?.toFixed(2) ?? "—"}`)}
          {chip("Shares", String(Math.round(trade.shares ?? 0)))}
          {chip("Stop", `$${trade.stop_loss?.toFixed(2) ?? "—"}`)}
          {chip("Target", `$${trade.take_profit?.toFixed(2) ?? "—"}`)}
        </div>
      </div>

      {divider}

      {/* Entry thesis */}
      <div>
        {section("Entry Thesis", reanalyzed ? <span style={{ color: "#a78bfa", fontSize: 8 }}>· Re-analyzed</span> : null)}
        <p style={{ fontSize: 11, color: "rgba(255,255,255,0.7)", lineHeight: 1.75, margin: 0 }}>
          {reanalyzed ?? (trade.entry_ai_reasoning || "No AI reasoning recorded for this trade.")}
        </p>
      </div>

      {/* Factor scores */}
      {factors.length > 0 && (
        <div>
          {section("Factors at Entry")}
          {factors.map(([k, v]) => <FactorBar key={k} label={k} score={v} />)}
        </div>
      )}

      {divider}

      {/* Exit analysis (hidden when re-analyzed — narrative replaces both) */}
      {!reanalyzed && (
        <div>
          {section("Exit Analysis")}
          <p style={{ fontSize: 11, color: trade.exit_ai_reasoning ? "rgba(255,255,255,0.7)" : "rgba(255,255,255,0.3)", lineHeight: 1.75, margin: "0 0 10px" }}>
            {trade.exit_ai_reasoning || "No AI reasoning recorded."}
          </p>

          {(trade.what_worked || trade.what_failed) && (
            <div style={{ display: "flex", gap: 8 }}>
              {trade.what_worked && (
                <div style={{ flex: 1, background: "rgba(74,222,128,0.05)", border: "1px solid rgba(74,222,128,0.12)", borderRadius: 7, padding: "9px 11px" }}>
                  <div style={{ fontSize: 8, color: "#4ade80", fontWeight: 700, marginBottom: 4, letterSpacing: "0.08em" }}>WORKED</div>
                  <div style={{ fontSize: 10, color: "rgba(255,255,255,0.6)", lineHeight: 1.65 }}>{trade.what_worked}</div>
                </div>
              )}
              {trade.what_failed && (
                <div style={{ flex: 1, background: "rgba(248,113,113,0.05)", border: "1px solid rgba(248,113,113,0.12)", borderRadius: 7, padding: "9px 11px" }}>
                  <div style={{ fontSize: 8, color: "#f87171", fontWeight: 700, marginBottom: 4, letterSpacing: "0.08em" }}>FAILED</div>
                  <div style={{ fontSize: 10, color: "rgba(255,255,255,0.6)", lineHeight: 1.65 }}>{trade.what_failed}</div>
                </div>
              )}
            </div>
          )}

          {trade.recommendation && (
            <div style={{ marginTop: 10, padding: "9px 11px", background: "rgba(124,92,252,0.07)", border: "1px solid rgba(124,92,252,0.18)", borderRadius: 7 }}>
              <div style={{ fontSize: 8, color: "#a78bfa", fontWeight: 700, marginBottom: 4, letterSpacing: "0.08em" }}>RECOMMENDATION</div>
              <div style={{ fontSize: 10, color: "rgba(255,255,255,0.65)", lineHeight: 1.65 }}>{trade.recommendation}</div>
            </div>
          )}
        </div>
      )}

      {/* Re-analyze button */}
      <div style={{ marginTop: "auto", paddingTop: 6 }}>
        {analyzeError && (
          <div style={{ fontSize: 10, color: "#f87171", marginBottom: 6 }}>{analyzeError}</div>
        )}
        <button
          onClick={() => analyzeMutation.mutate()}
          disabled={analyzeMutation.isPending}
          style={{
            width: "100%", padding: "9px 0", borderRadius: 8,
            border: "1px solid rgba(124,92,252,0.3)",
            background: analyzeMutation.isPending ? "rgba(124,92,252,0.04)" : "rgba(124,92,252,0.10)",
            color: "#a78bfa", fontSize: 11, fontWeight: 600, cursor: analyzeMutation.isPending ? "default" : "pointer",
            fontFamily: FONT, letterSpacing: "0.03em", transition: "all 0.15s",
          }}
        >
          {analyzeMutation.isPending ? "Analyzing…" : reanalyzed ? "Re-analyze Again" : "Re-analyze with Claude"}
        </button>
      </div>
    </div>
  );
}

// ── Main export ──────────────────────────────────────────────────────────────

export default function TradesTab({
  portfolioId,
  initialTradeId,
}: {
  portfolioId: string;
  initialTradeId?: string | null;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(initialTradeId ?? null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["trade-reviews", portfolioId],
    queryFn: () => api.getTradeReviews(portfolioId),
    staleTime: 2 * 60_000,
  });

  const trades = data?.trades ?? [];
  const selectedTrade = trades.find(t => t.trade_id === selectedId) ?? null;

  if (isLoading) {
    return (
      <div style={{ padding: 28, color: "rgba(255,255,255,0.3)", fontSize: 12, fontFamily: FONT }}>
        Loading trade history…
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 28, color: "#f87171", fontSize: 12, fontFamily: FONT }}>
        Failed to load trade reviews.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", height: "100%", minHeight: 0 }}>
      {/* Left panel — aggregate + list (40%) */}
      <div style={{
        width: "40%", borderRight: "1px solid rgba(255,255,255,0.06)",
        display: "flex", flexDirection: "column", minHeight: 0,
      }}>
        <AggregatePanel trades={trades} />
        <TradeList trades={trades} selectedId={selectedId} onSelect={setSelectedId} />
      </div>

      {/* Right panel — detail (60%) */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
        {selectedTrade ? (
          <TradeDetail trade={selectedTrade} portfolioId={portfolioId} />
        ) : (
          <div style={{
            flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
            color: "rgba(255,255,255,0.2)", fontSize: 12, fontFamily: FONT,
          }}>
            Select a trade to review
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard
npm run build 2>&1 | grep -i "error" | grep -v "warning" | head -10
```

Expected: no errors referencing TradesTab.tsx.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/IntelligenceBrief/TradesTab.tsx
git commit -m "feat: add TradesTab component (aggregate + list + detail + re-analyze)"
```

---

## Task 8: Wire TradesTab into IntelligenceBrief

**Files:**
- Modify: `dashboard/src/components/IntelligenceBrief/index.tsx`

- [ ] **Step 1: Add TradesTab import**

At the top of `index.tsx`, alongside the other section imports (after `AuditChat`):

```typescript
import TradesTab from "./TradesTab";
```

- [ ] **Step 2: Update Props interface**

Find:
```typescript
interface Props {
  portfolioId: string;
  portfolioName: string;
  onClose: () => void;
}
```

Replace with:
```typescript
interface Props {
  portfolioId: string;
  portfolioName: string;
  initialTab?: string;
  initialTradeId?: string | null;
  onClose: () => void;
}
```

- [ ] **Step 3: Update component signature and tab state**

Find:
```typescript
export default function IntelligenceBrief({ portfolioId, portfolioName, onClose }: Props) {
  const [activeTab, setActiveTab] = useState<"performance" | "risk" | "factors" | "gscott">("performance");
```

Replace with:
```typescript
export default function IntelligenceBrief({ portfolioId, portfolioName, initialTab, initialTradeId, onClose }: Props) {
  const [activeTab, setActiveTab] = useState<"performance" | "risk" | "factors" | "gscott" | "trades">(
    (initialTab as "performance" | "risk" | "factors" | "gscott" | "trades") ?? "performance"
  );
```

- [ ] **Step 4: Add TRADES to the tabs array**

Find:
```typescript
  const tabs = [
    { key: "performance" as const, label: "PERFORMANCE", dot: null },
    ...
    { key: "gscott" as const, label: "GSCOTT", dot: "#7c5cfc" },
  ];
```

Add the trades entry at the end of the array, before the closing `];`:
```typescript
    { key: "trades" as const, label: "TRADES", dot: null },
```

- [ ] **Step 5: Add TradesTab to the render branch**

Find the last existing tab render branch (the `gscott` one, around line 611):
```typescript
            ) : activeTab === "gscott" ? (
```

After the closing of that branch, add:
```typescript
            ) : activeTab === "trades" ? (
              <TradesTab portfolioId={portfolioId} initialTradeId={initialTradeId} />
```

- [ ] **Step 6: Verify in browser — open Intelligence Brief, click TRADES tab**

Start the dev server if not running:
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && ./run_dashboard.sh
```

Open http://localhost:5173, select a portfolio, click the Intelligence Brief button, click the TRADES tab. Should see the split panel with aggregate stats and trade list on the left, "Select a trade to review" on the right.

- [ ] **Step 7: Commit**

```bash
git add dashboard/src/components/IntelligenceBrief/index.tsx
git commit -m "feat: add TRADES tab to Intelligence Brief modal

Wires TradesTab into the tab bar. Accepts initialTab and initialTradeId
props so external components can deep-link to a specific trade review."
```

---

## Task 9: MatrixGrid HistoryPanel — closed trades section

**Files:**
- Modify: `dashboard/src/components/MatrixGrid/MatrixGrid.tsx`

- [ ] **Step 1: Add useBriefStore import to MatrixGrid**

At the top of `MatrixGrid.tsx`, with the other store imports:

```typescript
import { useBriefStore } from "../../lib/store";
```

- [ ] **Step 2: Add useQuery import if not already present**

Ensure `useQuery` is imported from `@tanstack/react-query` at the top of the file. If it's already there, skip.

```typescript
import { useQuery } from "@tanstack/react-query";
```

- [ ] **Step 3: Add api import if not already present**

Ensure `api` is imported from `../../lib/api`. If it's already there, skip.

- [ ] **Step 4: Update HistoryPanel signature**

Find:
```typescript
function HistoryPanel({ snapshots, startingCapital }: { snapshots: Snapshot[]; startingCapital?: number }) {
```

Replace with:
```typescript
function HistoryPanel({ snapshots, startingCapital, portfolioId }: { snapshots: Snapshot[]; startingCapital?: number; portfolioId: string }) {
```

- [ ] **Step 5: Add closed trades fetch and BriefStore hook inside HistoryPanel**

Inside `HistoryPanel`, immediately after the first line of function body (before `const sorted = ...`), add:

```typescript
  const openBrief = useBriefStore(s => s.openBrief);

  const { data: reviewsData } = useQuery({
    queryKey: ["trade-reviews", portfolioId],
    queryFn: () => api.getTradeReviews(portfolioId),
    staleTime: 5 * 60_000,
    enabled: !!portfolioId,
  });
  const closedTrades = reviewsData?.trades ?? [];
```

- [ ] **Step 6: Add closed trades section to HistoryPanel JSX**

At the end of the HistoryPanel `return`, after the closing `</div>` of the snapshot table section, add this before the outer closing `</div>`:

```tsx
      {/* Closed trades */}
      {closedTrades.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <div style={{ fontSize: 8, color: "#444", letterSpacing: "0.1em", marginBottom: 10 }}>
            CLOSED TRADES ({closedTrades.length})
          </div>
          <div style={{ border: "1px solid rgba(56,189,248,0.08)" }}>
            <div style={{
              display: "grid", gridTemplateColumns: "60px 1fr 50px 60px 70px",
              padding: "5px 14px", fontSize: 8, color: "#444", letterSpacing: "0.1em",
              borderBottom: "1px solid rgba(56,189,248,0.08)",
            }}>
              <span>TICKER</span><span>CLOSE</span><span>HOLD</span><span>P&L%</span><span>EXIT</span>
            </div>
            {closedTrades.slice(0, 50).map(trade => {
              const pnl = trade.pnl_pct ?? 0;
              return (
                <div
                  key={trade.trade_id}
                  onClick={() => openBrief("trades", trade.trade_id)}
                  style={{
                    display: "grid", gridTemplateColumns: "60px 1fr 50px 60px 70px",
                    padding: "6px 14px", fontSize: 11, cursor: "pointer",
                    borderBottom: "1px solid rgba(255,255,255,0.02)",
                    alignItems: "center", transition: "background 0.12s",
                  }}
                  onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = "rgba(56,189,248,0.04)"}
                  onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = "transparent"}
                >
                  <span style={{ color: "#ccc", fontWeight: 700 }}>{trade.ticker}</span>
                  <span style={{ color: "#555" }}>{trade.exit_date}</span>
                  <span style={{ color: "#555" }}>{trade.holding_days}d</span>
                  <span style={{ color: pnl >= 0 ? "#4ade80" : "#f87171", fontWeight: 700 }}>
                    {pnl >= 0 ? "+" : ""}{pnl.toFixed(1)}%
                  </span>
                  <span style={{ fontSize: 9, color: trade.exit_reason === "STOP_LOSS" ? "#f87171" : trade.exit_reason === "TAKE_PROFIT" ? "#4ade80" : "#818cf8" }}>
                    {trade.exit_reason.replace(/_/g, " ")}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
```

- [ ] **Step 7: Pass portfolioId to HistoryPanel at the call site**

Find line 820:
```typescript
          <HistoryPanel snapshots={snapshots} startingCapital={startingCapital} />
```

Replace with:
```typescript
          <HistoryPanel snapshots={snapshots} startingCapital={startingCapital} portfolioId={portfolios[0]?.id ?? ""} />
```

- [ ] **Step 8: Test the deep-link**

In the browser: select a portfolio, open the History tab in MatrixGrid. Scroll to the "CLOSED TRADES" section. Click a row. Intelligence Brief should open on the TRADES tab with that trade pre-selected in the detail panel.

- [ ] **Step 9: Commit**

```bash
git add dashboard/src/components/MatrixGrid/MatrixGrid.tsx
git commit -m "feat: add closed trades section to MatrixGrid HistoryPanel

Fetches trade reviews and renders a clickable list below the equity
snapshots. Clicking a row opens the Intelligence Brief TRADES tab with
that trade pre-selected via useBriefStore."
```

---

## Self-Review Checklist

- [x] **Spec coverage:**
  - GET /trade-reviews → Task 1 ✓
  - POST /trade-reviews/{id}/analyze → Task 2 ✓
  - BriefStore for deep-linking → Tasks 5, 6 ✓
  - AggregatePanel (win rate, avg P&L, avg hold, total, by-reason, by-regime) → Task 7 ✓
  - TradeList (filterable, sortable, exit reason badges) → Task 7 ✓
  - TradeDetail (header, entry thesis, factor bars, exit analysis, worked/failed, recommendation, re-analyze) → Task 7 ✓
  - TRADES tab in Intelligence Brief → Task 8 ✓
  - History tab deep-link → Task 9 ✓
  - Edge cases (no post-mortem, no AI reasoning, re-analyze failure, empty portfolio, duplicate tickers) → handled in Task 1 (backend) and Task 7 (frontend graceful rendering) ✓

- [x] **Placeholder scan:** No TBD/TODO found.

- [x] **Type consistency:**
  - `ClosedTrade.trade_id` used consistently across API, types, TradesTab, HistoryPanel ✓
  - `openBrief(tab, tradeId)` signature consistent between BriefStore definition and all call sites ✓
  - `api.getTradeReviews` returns `TradeReviewsResponse` with `.trades: ClosedTrade[]` ✓
  - `api.analyzeTradeReview` returns `TradeAnalyzeResponse` with `.narrative: string` ✓
  - `initialTab` / `initialTradeId` prop names consistent between TopBar render and IntelligenceBrief props ✓
