# CLAUDE.md — MicroCapRebuilder (Mommy Bot)

## Rules for AI Assistants

### Workflow Rules
- **Plan before coding.** For anything beyond a trivial fix, enter plan mode first. Outline the approach, get approval, then implement.
- **Verify before claiming success.** After making changes, run the dev server or relevant script and check output for errors. Do NOT claim something works without proof.
- **Preserve existing functionality.** When rewriting or refactoring, enumerate what currently works and confirm with the user what should be kept. Never silently remove features.
- **Don't deploy unless asked.** If asked to implement or fix something, do exactly that. Don't push, deploy, or change scope without explicit approval.
- **Update this file.** After completing a major feature or phase, update this CLAUDE.md to reflect the current state of the project.
- **Use python3**, not python, on this machine.
- **Always `except Exception as e:`** — never bare `except:`. It hides real bugs.

### Code Conventions
- Python 3 shebang: `#!/usr/bin/env python3`
- Use `pathlib.Path` for all file paths: `Path(__file__).parent.parent / "data"`
- Imports from `schema.py` for consistent column names
- All parameters from `data/config.json` — don't hardcode
- TypeScript for all frontend code (React dashboard)

## Project Overview

MicroCapRebuilder (aka **Mommy Bot**) is an intelligent, adaptive portfolio trading system for microcap stocks. Currently in **PAPER mode**.

**Core capabilities:**
- Multi-factor stock scoring (momentum, volatility, volume, relative strength, RSI, mean reversion)
- Market regime detection (bull/bear/sideways)
- Automated risk management (stop losses, take profits, position sizing)
- Unified analysis pipeline with optional AI review
- Learning pipeline (factor scores at entry, post-mortems at exit, weight adjustment)
- Risk scoreboard and early warning system
- React dashboard with FastAPI backend ("Mommy" co-pilot personality)

## Architecture

The system has three layers:

### 1. Python Backend (`scripts/`)
Core trading logic, analysis, and data management.

**Single source of truth:** `portfolio_state.py`
```python
from portfolio_state import load_portfolio_state, PortfolioState
state = load_portfolio_state(fetch_prices=True)  # or False for cached
```
All scripts consume `PortfolioState` — no direct CSV reads/writes for trading data. Regime cached with 1hr TTL. Price fetching uses yfinance batch download.

### 2. FastAPI API (`api/`)
Thin REST layer over existing Python modules. No business logic here.

### 3. React Dashboard (`dashboard/`)
Vite + React 19 + Tailwind v4 + TanStack Query + Zustand.

## Directory Structure

```
MicroCapRebuilder/
├── scripts/                     # Python backend (all trading logic)
│   ├── portfolio_state.py       # ⭐ Single source of truth for all portfolio data
│   ├── unified_analysis.py      # ANALYZE → EXECUTE pipeline
│   ├── ai_review.py             # AI review layer (APPROVE/MODIFY/VETO)
│   ├── execute_sells.py         # Stop loss / take profit execution
│   ├── pick_from_watchlist.py   # Multi-factor scoring and buy proposals
│   ├── update_positions.py      # Position price updates + daily snapshot
│   ├── stock_scorer.py          # 6-factor scoring model
│   ├── market_regime.py         # Bull/bear/sideways detection
│   ├── risk_manager.py          # Position sizing, concentration limits
│   ├── risk_scoreboard.py       # Overall risk score (5 components)
│   ├── analytics.py             # Sharpe, drawdown, CAGR, etc.
│   ├── trade_analyzer.py        # Completed trade analysis
│   ├── strategy_health.py       # Strategy A-F grading
│   ├── strategy_pivot.py        # PIVOT recommendations
│   ├── early_warning.py         # Proactive risk alerts
│   ├── factor_learning.py       # Factor weight adjustment from real trades
│   ├── post_mortem.py           # Trade post-mortem generation
│   ├── capital_preservation.py  # Capital preservation system
│   ├── portfolio_chat.py        # Mommy chat interface
│   ├── data_provider.py         # Centralized yfinance data access
│   ├── schema.py                # Column constants and enums
│   ├── explainability.py        # Trade rationale generation
│   ├── attribution.py           # Factor attribution analysis
│   ├── pattern_detector.py      # Pattern detection from trade history
│   ├── generate_report.py       # Daily text report
│   ├── generate_graph.py        # Performance chart generation
│   ├── webapp.py                # Legacy Streamlit dashboard (being replaced)
│   └── paper_trading.py         # Paper trading mode
├── api/                         # FastAPI REST layer
│   ├── main.py                  # App, CORS, lifespan
│   ├── deps.py                  # Shared dependencies (state loading)
│   └── routes/
│       ├── state.py             # GET /api/state, /api/state/refresh
│       ├── analysis.py          # POST /api/analyze, /api/execute
│       ├── risk.py              # GET /api/risk, /api/warnings
│       ├── performance.py       # GET /api/performance, /api/learning
│       ├── chat.py              # POST /api/chat, GET /api/mommy/insight
│       └── controls.py          # Paper/live mode, close-all
├── dashboard/                   # React SPA
│   ├── src/
│   │   ├── App.tsx              # Four-panel layout shell
│   │   ├── components/          # TopBar, PositionsPanel, RightPanel, etc.
│   │   ├── hooks/               # usePortfolioState, useRisk, usePerformance
│   │   └── lib/                 # api.ts, types.ts, store.ts
│   ├── vite.config.ts
│   └── package.json
├── data/                        # Data files (CSVs gitignored)
│   ├── config.json              # ⭐ All trading parameters
│   ├── positions.csv            # Current holdings
│   ├── transactions.csv         # Unified transaction ledger
│   └── daily_snapshots.csv      # Equity curve data
├── docs/plans/                  # Design documents
├── run_dashboard.sh             # Launches API (8000) + React dev (5173)
├── run_daily.sh                 # Daily trading pipeline
└── requirements.txt
```

## Trading Flow

### Daily Pipeline (`run_daily.sh`)
```
load_portfolio_state()
    → execute_sells(state)      # Check stop/target triggers
    → pick_from_watchlist(state) # Score candidates, propose buys
    → update_positions(state)    # Update prices, save snapshot
    → generate_graph()           # Performance chart
```

### ANALYZE → EXECUTE Flow (Dashboard)
```
ANALYZE button → run_unified_analysis(dry_run=True)
    1. Check stop/target triggers → proposed sells
    2. Score watchlist → proposed buys (limited by remaining cash)
    3. AI reviews proposals (batched, 10 at a time)
    → Show results with quant scores + AI reasoning
EXECUTE button → execute_approved_actions()
```

### Key Configuration (`data/config.json`)
- Starting capital: $50,000
- Risk per trade: 10%
- Max position: 15% of portfolio
- Max positions: 15
- Stop loss: 8%, Take profit: 20%
- Benchmark: ^RUT (fallback: IWM)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/state` | Portfolio state (fetch_prices=False) |
| GET | `/api/state/refresh` | Portfolio state (fetch_prices=True) |
| POST | `/api/analyze` | Run unified analysis (dry run) |
| POST | `/api/execute` | Execute approved actions |
| GET | `/api/risk` | Risk scoreboard + components |
| GET | `/api/warnings` | Early warnings |
| GET | `/api/performance` | Strategy health, analytics, attribution |
| GET | `/api/learning` | Factor summary + weight suggestions |
| POST | `/api/chat` | Mommy chat |
| GET | `/api/mommy/insight` | Context-aware rotating insight |

## React Dashboard

**Launch:** `./run_dashboard.sh` (starts API on 8000 + React on 5173)

**Stack:** Vite + React 19 + Tailwind v4 + TanStack Query + Zustand

**Layout:** Four persistent panels — positions (left), context tabs (right), activity feed (bottom-left), Mommy co-pilot (bottom-right). Top bar always visible with equity, day P&L, risk score, regime, action badges.

**Keyboard shortcuts:** A = analyze, E = execute, R = refresh, Escape = close detail

**Note:** `react-resizable-panels` v4 uses `Group`, `Panel`, `Separator` — NOT PanelGroup/PanelResizeHandle.

## Scoring Model

6 factors (weights in parentheses):
- **Momentum (30%)**: 20-day price change
- **Relative Strength (25%)**: Performance vs Russell 2000
- **Volatility (20%)**: Lower volatility = higher score
- **Volume (15%)**: Recent vs average volume (liquidity)
- **Mean Reversion (10%)**: Distance from 20-day SMA
- **RSI**: Overbought filter (score of 10.0 for overbought stocks)

ATR% calculated for volatility-adjusted position sizing.

**StockScore is a dataclass with individual attributes, not a dict:**
```python
factor_scores = {
    "momentum": s.momentum_score,
    "volatility": s.volatility_score,
    "volume": s.volume_score,
    "relative_strength": s.relative_strength_score,
    "mean_reversion": s.mean_reversion_score,
    "rsi": s.rsi_score,
}
```

## Learning Pipeline

- Factor scores recorded as JSON on each BUY transaction
- Post-mortems generated on each SELL (`data/post_mortems.csv`)
- `factor_learning.py` correlates entry scores with trade outcomes, adjusts weights +/-5% per cycle
- Minimum 20 completed trades before any adjustment
- No factor below 5% or above 40% weight

## Risk & Strategy Systems

- **Risk Scoreboard** (`risk_scoreboard.py`): Overall score from 5 components — Concentration, Drawdown, Exposure, Volatility, Stop Proximity
- **Early Warnings** (`early_warning.py`): Regime shifts, drawdown thresholds, losing streaks, concentration risk
- **Strategy Health** (`strategy_health.py`): A-F grading across Performance, Risk Control, Trading Edge, Factor Alignment, Market Fit
- **PIVOT Analysis** (`strategy_pivot.py`): Recommends Consolidation/Defensive/Cash/Aggressive/Regime Adaptation modes
- **Capital Preservation** (`capital_preservation.py`): `PreservationStatus` is a dataclass — use `.active` not `.get()`

## Known Gotchas

- `ALE` ticker appears delisted — fails price fetch consistently
- `stale_alerts` must load from tracker file even when `fetch_prices=False`
- `FactorLearner.get_factor_summary()` is a method, not a module-level function
- AI JSON responses need cleaning: strip markdown blocks, find JSON boundaries, remove trailing commas, batch 10 max
- Cash must be tracked as buys are proposed — each position capped by remaining cash
- Pandas Series vs scalar: `.iloc[0]` when you expect a scalar from a filtered DataFrame

## Data Schemas

### transactions.csv
```
transaction_id, date, ticker, action, shares, price, total_value,
stop_loss, take_profit, reason, factor_scores, regime_at_entry
```
Actions: `BUY`, `SELL` | Reasons: `SIGNAL`, `STOP_LOSS`, `TAKE_PROFIT`, `MANUAL`, `MIGRATION`

### positions.csv
```
ticker, shares, avg_cost_basis, current_price, market_value,
unrealized_pnl, unrealized_pnl_pct, stop_loss, take_profit, entry_date
```

### daily_snapshots.csv
```
date, cash, positions_value, total_equity, day_pnl, day_pnl_pct, benchmark_value
```

## Files That Are Gitignored
- `data/*.csv` (config.json is tracked via `!data/config.json`)
- `charts/`, `reports/`, `backup/`, `logs/`
- `.venv/`, `__pycache__/`, `node_modules/`
