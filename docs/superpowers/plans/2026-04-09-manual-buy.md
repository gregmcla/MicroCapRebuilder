# Manual Buy Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the ability to manually buy any ticker from the dashboard via a top-bar BUY button with auto-suggested share count, editable stop/target, and trade preview.

**Architecture:** New `POST /api/{portfolio_id}/buy` endpoint for execution + `GET /api/{portfolio_id}/quote/{ticker}` for price/config lookup. New `BuyModal` component triggered from a top-bar BUY button. Follows the existing SellModal pattern exactly.

**Tech Stack:** Python/FastAPI (backend), React 19 + TypeScript (frontend), TanStack Query for cache invalidation.

**Spec:** `docs/superpowers/specs/2026-04-09-manual-buy-design.md`

---

### Task 1: Add quote endpoint to backend

**Files:**
- Modify: `/Users/gregmclaughlin/MicroCapRebuilder/api/routes/controls.py`

- [ ] **Step 1: Add the quote endpoint**

Add this endpoint to `api/routes/controls.py`, after the existing imports. Add `import math` and `from data_files import load_config` to the imports at the top, and `import yfinance as yf` and `from threading import Thread`:

```python
@router.get("/quote/{ticker}")
def get_quote(portfolio_id: str, ticker: str):
    """Get live price + portfolio risk defaults for a ticker."""
    from portfolio_state import fetch_prices_batch
    import yfinance as yf
    from threading import Thread

    # Fetch live price
    prices, failures, prev_closes = fetch_prices_batch([ticker])
    if ticker in failures or ticker not in prices:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {ticker}")

    price = prices[ticker]
    prev_close = prev_closes.get(ticker)

    # Fetch company info with timeout
    info_result = {}
    def fetch_info():
        try:
            data = yf.Ticker(ticker).info
            info_result["name"] = data.get("shortName", data.get("longName", ticker))
            info_result["sector"] = data.get("sector", "")
        except Exception:
            pass

    t = Thread(target=fetch_info)
    t.start()
    t.join(timeout=5)

    # Portfolio config defaults
    config = load_config(portfolio_id)
    risk_pct = config.get("risk_per_trade_pct", 8.0)
    stop_pct = config.get("default_stop_loss_pct", 7.0)
    take_pct = config.get("default_take_profit_pct", 20.0)

    # Cash
    state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
    cash = state.cash

    suggested = math.floor(cash * risk_pct / 100 / price) if price > 0 else 0

    return {
        "ticker": ticker.upper(),
        "price": round(price, 2),
        "name": info_result.get("name", ticker),
        "sector": info_result.get("sector", ""),
        "prev_close": round(prev_close, 2) if prev_close else None,
        "available_cash": round(cash, 2),
        "risk_per_trade_pct": risk_pct,
        "default_stop_loss_pct": stop_pct,
        "default_take_profit_pct": take_pct,
        "suggested_shares": suggested,
    }
```

- [ ] **Step 2: Add missing imports to the top of controls.py**

Add `import math` to the imports section at the top of the file. Add `from data_files import load_config` — `load_config` is already importable from `data_files` (currently only `is_paper_mode, set_paper_mode` are imported). Update the import line:

```python
from data_files import is_paper_mode, set_paper_mode, load_config
```

- [ ] **Step 3: Verify endpoint works**

Run: `curl -s http://localhost:8001/api/max/quote/AAPL | python3 -m json.tool`

Expected: JSON with `ticker`, `price`, `name`, `sector`, `available_cash`, `suggested_shares`, etc.

- [ ] **Step 4: Commit**

```bash
git add api/routes/controls.py
git commit -m "feat: add GET /api/{portfolio_id}/quote/{ticker} endpoint for manual buy"
```

---

### Task 2: Add buy endpoint to backend

**Files:**
- Modify: `/Users/gregmclaughlin/MicroCapRebuilder/api/routes/controls.py`

- [ ] **Step 1: Add BuyRequest model**

Add after `SellRequest` in `controls.py`:

```python
class BuyRequest(BaseModel):
    ticker: str
    shares: int
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
```

- [ ] **Step 2: Add buy endpoint**

Add the `update_position` import to the existing `portfolio_state` import block:

```python
from portfolio_state import (
    load_portfolio_state,
    save_transactions_batch,
    remove_position,
    reduce_position,
    update_position,
    save_positions,
)
```

Then add the endpoint:

```python
@router.post("/buy")
def buy_position(portfolio_id: str, body: BuyRequest):
    """Manually buy a position at market price."""
    from portfolio_state import fetch_prices_batch

    if body.shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be positive")

    # Fetch live price
    prices, failures, _ = fetch_prices_batch([body.ticker])
    if body.ticker in failures or body.ticker not in prices:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {body.ticker}")

    price = prices[body.ticker]

    # Load state for cash check
    state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
    total_cost = body.shares * price

    if total_cost > state.cash + 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient cash: need ${total_cost:,.2f}, have ${state.cash:,.2f}",
        )

    # Stop/take profit from request or config defaults
    config = load_config(portfolio_id)
    stop_pct = body.stop_loss_pct if body.stop_loss_pct is not None else config.get("default_stop_loss_pct", 7.0)
    take_pct = body.take_profit_pct if body.take_profit_pct is not None else config.get("default_take_profit_pct", 20.0)
    stop_loss = round(price * (1 - stop_pct / 100), 2)
    take_profit = round(price * (1 + take_pct / 100), 2)

    transaction = {
        "transaction_id": f"BUY_{body.ticker}_{date.today().isoformat()}",
        "date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "ticker": body.ticker,
        "action": "BUY",
        "shares": body.shares,
        "price": round(price, 2),
        "total_value": round(total_cost, 2),
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "reason": "MANUAL",
        "factor_scores": "{}",
        "regime_at_entry": "",
    }

    # Save transaction BEFORE updating position
    state = save_transactions_batch(state, [transaction])
    state = update_position(state, body.ticker, body.shares, price, stop_loss, take_profit)
    save_positions(state)

    return {
        "ticker": body.ticker,
        "shares": body.shares,
        "price": round(price, 2),
        "total_value": round(total_cost, 2),
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "remaining_cash": round(state.cash, 2),
        "message": f"Bought {body.shares} shares of {body.ticker} @ ${price:.2f} for ${total_cost:,.2f}",
    }
```

- [ ] **Step 3: Verify endpoint works (dry test with small buy)**

Run: `curl -s -X POST http://localhost:8001/api/max/buy -H "Content-Type: application/json" -d '{"ticker":"AAPL","shares":1}' | python3 -m json.tool`

Expected: JSON with `ticker`, `shares`, `price`, `total_value`, `remaining_cash`, `message`.

- [ ] **Step 4: Commit**

```bash
git add api/routes/controls.py
git commit -m "feat: add POST /api/{portfolio_id}/buy endpoint for manual buys"
```

---

### Task 3: Add API client functions

**Files:**
- Modify: `/Users/gregmclaughlin/MicroCapRebuilder/dashboard/src/lib/api.ts`

- [ ] **Step 1: Add getQuote and buyPosition functions**

Add after the `sellPosition` function in the `api` object:

```typescript
  getQuote: (pid: string, ticker: string) =>
    get<{
      ticker: string;
      price: number;
      name: string;
      sector: string;
      prev_close: number | null;
      available_cash: number;
      risk_per_trade_pct: number;
      default_stop_loss_pct: number;
      default_take_profit_pct: number;
      suggested_shares: number;
    }>(`/${pid}/quote/${ticker}`),

  buyPosition: (pid: string, body: {
    ticker: string;
    shares: number;
    stop_loss_pct?: number;
    take_profit_pct?: number;
  }) =>
    post<{
      ticker: string;
      shares: number;
      price: number;
      total_value: number;
      stop_loss: number;
      take_profit: number;
      remaining_cash: number;
      message: string;
    }>(`/${pid}/buy`, body),
```

- [ ] **Step 2: TypeScript check**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npx tsc --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/lib/api.ts
git commit -m "feat: add getQuote and buyPosition API client functions"
```

---

### Task 4: Build BuyModal component

**Files:**
- Create: `/Users/gregmclaughlin/MicroCapRebuilder/dashboard/src/components/BuyModal.tsx`

- [ ] **Step 1: Create BuyModal**

```typescript
/** BuyModal — manual buy with ticker input, auto-suggested shares, editable stop/target. */

import { useState, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { usePortfolioStore } from "../lib/store";
import { api } from "../lib/api";

interface QuoteData {
  ticker: string;
  price: number;
  name: string;
  sector: string;
  prev_close: number | null;
  available_cash: number;
  risk_per_trade_pct: number;
  default_stop_loss_pct: number;
  default_take_profit_pct: number;
  suggested_shares: number;
}

interface BuyModalProps {
  onClose: () => void;
}

export default function BuyModal({ onClose }: BuyModalProps) {
  const queryClient = useQueryClient();
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);

  // Stage 1: ticker input
  const [tickerInput, setTickerInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tickerRef = useRef<HTMLInputElement>(null);

  // Stage 2: trade form (after quote loaded)
  const [quote, setQuote] = useState<QuoteData | null>(null);
  const [shares, setShares] = useState("");
  const [stopPct, setStopPct] = useState("");
  const [takePct, setTakePct] = useState("");
  const [buying, setBuying] = useState(false);
  const [result, setResult] = useState<{ message: string; success: boolean } | null>(null);

  useEffect(() => { tickerRef.current?.focus(); }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const fetchQuote = async () => {
    const ticker = tickerInput.trim().toUpperCase();
    if (!ticker) return;
    setLoading(true);
    setError(null);
    try {
      const q = await api.getQuote(portfolioId, ticker);
      setQuote(q);
      setShares(String(q.suggested_shares));
      setStopPct(String(q.default_stop_loss_pct));
      setTakePct(String(q.default_take_profit_pct));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch quote");
    } finally {
      setLoading(false);
    }
  };

  const numShares = Math.floor(Number(shares) || 0);
  const totalCost = quote ? numShares * quote.price : 0;
  const isValid = quote != null && numShares > 0 && totalCost <= quote.available_cash;
  const stopPrice = quote ? quote.price * (1 - (Number(stopPct) || 0) / 100) : 0;
  const targetPrice = quote ? quote.price * (1 + (Number(takePct) || 0) / 100) : 0;

  const handleBuy = async () => {
    if (!isValid || !quote) return;
    setBuying(true);
    try {
      const res = await api.buyPosition(portfolioId, {
        ticker: quote.ticker,
        shares: numShares,
        stop_loss_pct: Number(stopPct) || undefined,
        take_profit_pct: Number(takePct) || undefined,
      });
      setResult({ message: res.message, success: true });
      queryClient.invalidateQueries({ queryKey: ["portfolioState"] });
      queryClient.invalidateQueries({ queryKey: ["chartData"] });
      setTimeout(() => onClose(), 2000);
    } catch (e) {
      setResult({ message: e instanceof Error ? e.message : "Buy failed", success: false });
    } finally {
      setBuying(false);
    }
  };

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
      onClick={onClose}
    >
      <div
        className="rounded-xl p-5 w-full"
        style={{
          maxWidth: "400px",
          background: "var(--surface-1)",
          border: "1px solid var(--border-2)",
          boxShadow: "0 24px 48px rgba(0,0,0,0.5)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <span className="font-mono font-bold" style={{ fontSize: "18px", color: "var(--text-4)" }}>
            {quote ? `Buy ${quote.ticker}` : "Manual Buy"}
          </span>
          <button
            onClick={onClose}
            className="text-xs rounded px-2 py-1 transition-colors"
            style={{ color: "var(--text-1)", border: "1px solid var(--border-1)" }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-1)"; }}
          >
            ESC
          </button>
        </div>

        {result ? (
          <div
            className="rounded-lg p-4 text-center"
            style={{
              background: result.success ? "rgba(74,222,128,0.08)" : "rgba(248,113,113,0.08)",
              border: `1px solid ${result.success ? "rgba(74,222,128,0.25)" : "rgba(248,113,113,0.25)"}`,
            }}
          >
            <span className="text-sm font-medium" style={{ color: result.success ? "var(--green)" : "var(--red)" }}>
              {result.message}
            </span>
          </div>
        ) : !quote ? (
          /* Stage 1: Ticker input */
          <div>
            <label
              className="block mb-1.5"
              style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-1)" }}
            >
              Ticker
            </label>
            <input
              ref={tickerRef}
              type="text"
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
              onKeyDown={(e) => { if (e.key === "Enter") fetchQuote(); }}
              placeholder="e.g. AAPL"
              className="w-full font-mono text-sm rounded px-3 py-2 outline-none transition-colors mb-3"
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--border-1)",
                color: "var(--text-4)",
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-1)"; }}
            />
            {error && (
              <div className="text-xs mb-3" style={{ color: "var(--red)" }}>{error}</div>
            )}
            <button
              onClick={fetchQuote}
              disabled={!tickerInput.trim() || loading}
              className="w-full py-2 rounded text-xs font-semibold transition-colors disabled:opacity-40"
              style={{
                background: "rgba(74,222,128,0.10)",
                color: "rgba(74,222,128,0.90)",
                border: "1px solid rgba(74,222,128,0.35)",
              }}
              onMouseEnter={(e) => {
                if (!e.currentTarget.disabled) {
                  e.currentTarget.style.background = "rgba(74,222,128,0.18)";
                  e.currentTarget.style.borderColor = "rgba(74,222,128,0.55)";
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "rgba(74,222,128,0.10)";
                e.currentTarget.style.borderColor = "rgba(74,222,128,0.35)";
              }}
            >
              {loading ? "Looking up..." : "Get Quote"}
            </button>
          </div>
        ) : (
          /* Stage 2: Trade form */
          <>
            {/* Company info */}
            <div
              className="rounded-lg p-3 mb-3"
              style={{ background: "var(--surface-2)", border: "1px solid var(--border-0)" }}
            >
              <div className="flex items-baseline justify-between">
                <div>
                  <span className="font-mono font-bold text-sm" style={{ color: "var(--text-4)" }}>{quote.ticker}</span>
                  <span className="text-xs ml-2" style={{ color: "var(--text-1)" }}>{quote.name}</span>
                </div>
                <span className="font-mono font-bold text-sm" style={{ color: "var(--green)" }}>${quote.price.toFixed(2)}</span>
              </div>
              {quote.sector && (
                <div className="text-xs mt-1" style={{ color: "var(--text-0)" }}>{quote.sector}</div>
              )}
              <button
                onClick={() => { setQuote(null); setError(null); }}
                className="text-xs mt-1"
                style={{ color: "var(--accent)", background: "none", border: "none", cursor: "pointer", padding: 0 }}
              >
                Change ticker
              </button>
            </div>

            {/* Shares input */}
            <div className="mb-3">
              <label
                className="block mb-1.5"
                style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-1)" }}
              >
                Shares
              </label>
              <div className="flex gap-2">
                <input
                  type="number"
                  min={1}
                  value={shares}
                  onChange={(e) => setShares(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleBuy(); }}
                  className="flex-1 font-mono text-sm rounded px-3 py-2 outline-none transition-colors"
                  style={{
                    background: "var(--surface-2)",
                    border: "1px solid var(--border-1)",
                    color: "var(--text-4)",
                  }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = "var(--border-1)"; }}
                />
                <span className="flex items-center text-xs font-mono" style={{ color: "var(--text-1)" }}>
                  suggested: {quote.suggested_shares.toLocaleString()}
                </span>
              </div>
            </div>

            {/* Stop / Target inputs */}
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <label
                  className="block mb-1.5"
                  style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--red)" }}
                >
                  Stop Loss %
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={stopPct}
                  onChange={(e) => setStopPct(e.target.value)}
                  className="w-full font-mono text-sm rounded px-3 py-2 outline-none transition-colors"
                  style={{
                    background: "var(--surface-2)",
                    border: "1px solid rgba(248,113,113,0.20)",
                    color: "var(--text-4)",
                  }}
                />
              </div>
              <div>
                <label
                  className="block mb-1.5"
                  style={{ fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--green)" }}
                >
                  Take Profit %
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={takePct}
                  onChange={(e) => setTakePct(e.target.value)}
                  className="w-full font-mono text-sm rounded px-3 py-2 outline-none transition-colors"
                  style={{
                    background: "var(--surface-2)",
                    border: "1px solid rgba(74,222,128,0.20)",
                    color: "var(--text-4)",
                  }}
                />
              </div>
            </div>

            {/* Trade preview */}
            {isValid && (
              <div
                className="rounded-lg p-3 mb-4 space-y-1.5"
                style={{ background: "var(--surface-2)", border: "1px solid var(--border-0)" }}
              >
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-1)" }}>Total Cost</span>
                  <span className="font-mono" style={{ color: "var(--text-3)" }}>
                    ${totalCost.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-1)" }}>% of Cash</span>
                  <span className="font-mono" style={{ color: "var(--text-3)" }}>
                    {((totalCost / quote.available_cash) * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--red)" }}>Stop</span>
                  <span className="font-mono" style={{ color: "var(--red)" }}>
                    ${stopPrice.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--green)" }}>Target</span>
                  <span className="font-mono" style={{ color: "var(--green)" }}>
                    ${targetPrice.toFixed(2)}
                  </span>
                </div>
                <div
                  className="flex justify-between text-xs pt-1.5 mt-1.5"
                  style={{ borderTop: "1px solid var(--border-1)" }}
                >
                  <span style={{ color: "var(--text-1)" }}>Remaining Cash</span>
                  <span className="font-mono" style={{ color: "var(--text-3)" }}>
                    ${(quote.available_cash - totalCost).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </span>
                </div>
              </div>
            )}

            {totalCost > quote.available_cash && numShares > 0 && (
              <div className="text-xs mb-3" style={{ color: "var(--red)" }}>
                Insufficient cash: need ${totalCost.toLocaleString(undefined, { maximumFractionDigits: 0 })}, have ${quote.available_cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2">
              <button
                onClick={onClose}
                className="flex-1 py-2 rounded text-xs font-semibold transition-colors"
                style={{
                  background: "var(--surface-3)",
                  color: "var(--text-2)",
                  border: "1px solid var(--border-1)",
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleBuy}
                disabled={!isValid || buying}
                className="flex-1 py-2 rounded text-xs font-semibold transition-colors disabled:opacity-40"
                style={{
                  background: "rgba(74,222,128,0.10)",
                  color: "rgba(74,222,128,0.90)",
                  border: "1px solid rgba(74,222,128,0.35)",
                }}
                onMouseEnter={(e) => {
                  if (!e.currentTarget.disabled) {
                    e.currentTarget.style.background = "rgba(74,222,128,0.18)";
                    e.currentTarget.style.borderColor = "rgba(74,222,128,0.55)";
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "rgba(74,222,128,0.10)";
                  e.currentTarget.style.borderColor = "rgba(74,222,128,0.35)";
                }}
              >
                {buying ? "Buying..." : `Buy ${numShares.toLocaleString()} ${quote.ticker}`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npx tsc --noEmit`

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/BuyModal.tsx
git commit -m "feat: add BuyModal component for manual buys"
```

---

### Task 5: Add BUY button to top bar

**Files:**
- Modify: `/Users/gregmclaughlin/MicroCapRebuilder/dashboard/src/components/TopBar.tsx`

- [ ] **Step 1: Add BuyButton import and state**

At the top of `TopBar.tsx`, add the import:

```typescript
import BuyModal from "./BuyModal";
```

- [ ] **Step 2: Add BuyButton inline component**

Add this before the `TopBar` component function (or at the top of the file after imports). Follow the pattern of existing buttons — a simple component with modal state:

```typescript
function BuyButton() {
  const [showModal, setShowModal] = useState(false);
  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        className="inline-flex items-center gap-1.5 font-semibold tracking-widest uppercase transition-all duration-150 rounded-[6px] border border-emerald-400/40 bg-emerald-400/[0.07] text-emerald-400 hover:border-emerald-400/70 hover:bg-emerald-400/[0.13]"
        style={{ fontSize: "10px", padding: "4px 10px", letterSpacing: "0.1em" }}
      >
        + BUY
      </button>
      {showModal && <BuyModal onClose={() => setShowModal(false)} />}
    </>
  );
}
```

- [ ] **Step 3: Add BuyButton to the actionButtons JSX**

In the `actionButtons` const, add `<BuyButton />` right after `<ScanButton />` and before the divider:

```typescript
      {!isOverviewOrLogs && (
        <>
          <UpdateButton />
          <ScanButton />
          <BuyButton />
          <div style={{ width: "1px", height: "18px", background: "var(--border-1)", flexShrink: 0 }} />
          <AnalyzeExecute />
          <div style={{ width: "1px", height: "18px", background: "var(--border-1)", flexShrink: 0 }} />
        </>
      )}
```

- [ ] **Step 4: Ensure `useState` is imported**

Check that `useState` is in the React import at the top. If not, add it:

```typescript
import { useState } from "react";
```

- [ ] **Step 5: TypeScript check + build**

Run: `cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && npx tsc --noEmit && npx vite build`

Expected: No errors, clean build.

- [ ] **Step 6: Restart API and verify**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && lsof -ti :8001 | xargs kill -9 2>/dev/null; sleep 1 && source .venv/bin/activate && DISABLE_SOCIAL=true nohup uvicorn api.main:app --host 0.0.0.0 --port 8001 > /tmp/mcr_api.log 2>&1 &
```

Wait 2s, then verify: `curl -s http://localhost:8001/api/health`

- [ ] **Step 7: Commit**

```bash
git add dashboard/src/components/TopBar.tsx
git commit -m "feat: add BUY button to top bar, opens BuyModal"
```
