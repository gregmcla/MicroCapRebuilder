# Multi-Portfolio Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add support for multiple independent portfolios, each with its own config, data directory, and trading parameters, with a unified dashboard overview.

**Architecture:** Thread `portfolio_id` through `data_files.py` → `portfolio_state.py` → API routes → React hooks. Each portfolio gets its own directory under `data/portfolios/{id}/`. A portfolio registry (`data/portfolios.json`) tracks all portfolios. The dashboard adds a portfolio switcher and aggregate overview page.

**Tech Stack:** Python 3 (FastAPI, pandas), React 19 + TypeScript, Tailwind v4, TanStack Query, Zustand

---

### Task 1: Portfolio Registry & Data Directory Setup

**Files:**
- Create: `data/portfolios.json`
- Create: `scripts/portfolio_registry.py`
- Modify: `scripts/data_files.py`

**Step 1: Create portfolio registry module**

Create `scripts/portfolio_registry.py`:

```python
#!/usr/bin/env python3
"""Portfolio registry — manages the list of portfolios and their metadata."""

import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

REGISTRY_FILE = Path(__file__).parent.parent / "data" / "portfolios.json"
PORTFOLIOS_DIR = Path(__file__).parent.parent / "data" / "portfolios"

# Universe presets: (default_stop_loss, risk_per_trade, factor weight overrides)
UNIVERSE_PRESETS = {
    "microcap": {
        "label": "Micro Cap (<$300M)",
        "default_stop_loss_pct": 8.0,
        "risk_per_trade_pct": 10.0,
        "max_position_pct": 15.0,
        "scoring_weights": {
            "momentum": 0.30, "relative_strength": 0.25,
            "volatility": 0.20, "volume": 0.15, "mean_reversion": 0.10
        },
        "benchmark_symbol": "^RUT",
        "fallback_benchmark": "IWM",
    },
    "smallcap": {
        "label": "Small Cap ($300M–$2B)",
        "default_stop_loss_pct": 7.0,
        "risk_per_trade_pct": 8.0,
        "max_position_pct": 12.0,
        "scoring_weights": {
            "momentum": 0.25, "relative_strength": 0.25,
            "volatility": 0.20, "volume": 0.15, "mean_reversion": 0.15
        },
        "benchmark_symbol": "^RUT",
        "fallback_benchmark": "IWM",
    },
    "midcap": {
        "label": "Mid Cap ($2B–$10B)",
        "default_stop_loss_pct": 6.0,
        "risk_per_trade_pct": 7.0,
        "max_position_pct": 10.0,
        "scoring_weights": {
            "momentum": 0.20, "relative_strength": 0.20,
            "volatility": 0.20, "volume": 0.15, "mean_reversion": 0.25
        },
        "benchmark_symbol": "^MID",
        "fallback_benchmark": "MDY",
    },
    "largecap": {
        "label": "Large Cap ($10B+)",
        "default_stop_loss_pct": 5.0,
        "risk_per_trade_pct": 6.0,
        "max_position_pct": 10.0,
        "scoring_weights": {
            "momentum": 0.15, "relative_strength": 0.30,
            "volatility": 0.20, "volume": 0.10, "mean_reversion": 0.25
        },
        "benchmark_symbol": "^GSPC",
        "fallback_benchmark": "SPY",
    },
    "custom": {
        "label": "Custom (user-defined)",
        "default_stop_loss_pct": 8.0,
        "risk_per_trade_pct": 10.0,
        "max_position_pct": 15.0,
        "scoring_weights": {
            "momentum": 0.30, "relative_strength": 0.25,
            "volatility": 0.20, "volume": 0.15, "mean_reversion": 0.10
        },
        "benchmark_symbol": "^GSPC",
        "fallback_benchmark": "SPY",
    },
}


@dataclass
class PortfolioMeta:
    id: str
    name: str
    universe: str
    created: str
    starting_capital: float
    active: bool = True


def load_registry() -> dict:
    """Load portfolio registry from disk."""
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE) as f:
            return json.load(f)
    return {"portfolios": [], "default_portfolio": None}


def save_registry(registry: dict) -> None:
    """Save portfolio registry to disk."""
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)


def list_portfolios(active_only: bool = True) -> list[PortfolioMeta]:
    """List all portfolios."""
    registry = load_registry()
    portfolios = []
    for p in registry.get("portfolios", []):
        if active_only and not p.get("active", True):
            continue
        portfolios.append(PortfolioMeta(**p))
    return portfolios


def get_default_portfolio_id() -> Optional[str]:
    """Get the default portfolio ID."""
    registry = load_registry()
    return registry.get("default_portfolio")


def get_portfolio_dir(portfolio_id: str) -> Path:
    """Get the data directory for a specific portfolio."""
    return PORTFOLIOS_DIR / portfolio_id


def create_portfolio(
    portfolio_id: str,
    name: str,
    universe: str,
    starting_capital: float,
) -> PortfolioMeta:
    """Create a new portfolio with universe-appropriate defaults."""
    from datetime import date

    registry = load_registry()

    # Check for duplicate ID
    existing_ids = {p["id"] for p in registry.get("portfolios", [])}
    if portfolio_id in existing_ids:
        raise ValueError(f"Portfolio '{portfolio_id}' already exists")

    # Create directory
    portfolio_dir = get_portfolio_dir(portfolio_id)
    portfolio_dir.mkdir(parents=True, exist_ok=True)

    # Build config from current microcap config as base, override with universe preset
    preset = UNIVERSE_PRESETS.get(universe, UNIVERSE_PRESETS["custom"])

    # Load existing config as template
    base_config_path = Path(__file__).parent.parent / "data" / "config.json"
    if base_config_path.exists():
        with open(base_config_path) as f:
            config = json.load(f)
    else:
        config = {}

    # Apply universe overrides
    config["starting_capital"] = starting_capital
    config["default_stop_loss_pct"] = preset["default_stop_loss_pct"]
    config["risk_per_trade_pct"] = preset["risk_per_trade_pct"]
    config["max_position_pct"] = preset["max_position_pct"]
    config["benchmark_symbol"] = preset["benchmark_symbol"]
    config["fallback_benchmark"] = preset["fallback_benchmark"]
    if "scoring_weights" in config:
        config["scoring_weights"]["default"] = preset["scoring_weights"]

    # Save portfolio config
    with open(portfolio_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    # Register portfolio
    meta = PortfolioMeta(
        id=portfolio_id,
        name=name,
        universe=universe,
        created=str(date.today()),
        starting_capital=starting_capital,
        active=True,
    )
    registry.setdefault("portfolios", []).append(asdict(meta))
    if registry.get("default_portfolio") is None:
        registry["default_portfolio"] = portfolio_id
    save_registry(registry)

    return meta


def archive_portfolio(portfolio_id: str) -> None:
    """Soft-delete a portfolio (set active=False)."""
    registry = load_registry()
    for p in registry.get("portfolios", []):
        if p["id"] == portfolio_id:
            p["active"] = False
            break
    save_registry(registry)
```

**Step 2: Modify `data_files.py` to accept optional `portfolio_id`**

Current `data_files.py` uses a module-level `DATA_DIR`. Add an optional `portfolio_id` parameter to all path functions. When provided, paths resolve to `data/portfolios/{id}/` instead of `data/`.

Changes to `scripts/data_files.py`:

Add after the imports (line 10):
```python
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
PORTFOLIOS_DIR = DATA_DIR / "portfolios"
CONFIG_FILE = DATA_DIR / "config.json"
```

Replace every path-returning function to accept `portfolio_id: str | None = None`:

```python
def _resolve_data_dir(portfolio_id: str | None = None) -> Path:
    """Resolve the data directory for a given portfolio or the global default."""
    if portfolio_id:
        d = PORTFOLIOS_DIR / portfolio_id
        if not d.exists():
            raise FileNotFoundError(f"Portfolio directory not found: {d}")
        return d
    return DATA_DIR


def load_config(portfolio_id: str | None = None) -> dict:
    """Load configuration from config.json."""
    data_dir = _resolve_data_dir(portfolio_id)
    config_file = data_dir / "config.json"
    if config_file.exists():
        with open(config_file) as f:
            return json.load(f)
    return {"starting_capital": 50000.0, "mode": "live"}


def save_config(config: dict, portfolio_id: str | None = None) -> None:
    """Save configuration to config.json."""
    data_dir = _resolve_data_dir(portfolio_id)
    config_file = data_dir / "config.json"
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)


def is_paper_mode(portfolio_id: str | None = None) -> bool:
    config = load_config(portfolio_id)
    return config.get("mode", "live") == "paper"


def set_paper_mode(enabled: bool, portfolio_id: str | None = None) -> None:
    config = load_config(portfolio_id)
    config["mode"] = "paper" if enabled else "live"
    save_config(config, portfolio_id)


def get_file_suffix(portfolio_id: str | None = None) -> str:
    return "_paper" if is_paper_mode(portfolio_id) else ""


def get_positions_file(portfolio_id: str | None = None) -> Path:
    data_dir = _resolve_data_dir(portfolio_id)
    suffix = get_file_suffix(portfolio_id)
    return data_dir / f"positions{suffix}.csv"


def get_transactions_file(portfolio_id: str | None = None) -> Path:
    data_dir = _resolve_data_dir(portfolio_id)
    suffix = get_file_suffix(portfolio_id)
    return data_dir / f"transactions{suffix}.csv"


def get_daily_snapshots_file(portfolio_id: str | None = None) -> Path:
    data_dir = _resolve_data_dir(portfolio_id)
    suffix = get_file_suffix(portfolio_id)
    return data_dir / f"daily_snapshots{suffix}.csv"


get_snapshots_file = get_daily_snapshots_file


def get_config_file(portfolio_id: str | None = None) -> Path:
    data_dir = _resolve_data_dir(portfolio_id)
    return data_dir / "config.json"


def get_watchlist_file(portfolio_id: str | None = None) -> Path:
    data_dir = _resolve_data_dir(portfolio_id)
    return data_dir / "watchlist.jsonl"


def get_all_data_files(portfolio_id: str | None = None) -> dict:
    data_dir = _resolve_data_dir(portfolio_id)
    suffix = get_file_suffix(portfolio_id)
    return {
        "positions": data_dir / f"positions{suffix}.csv",
        "transactions": data_dir / f"transactions{suffix}.csv",
        "snapshots": data_dir / f"daily_snapshots{suffix}.csv",
    }
```

All callers that don't pass `portfolio_id` continue to work exactly as before (backward compatible).

**Step 3: Create migration script**

Create `scripts/migrate_to_portfolios.py`:

```python
#!/usr/bin/env python3
"""One-time migration: move flat data files into data/portfolios/microcap/."""

import json
import shutil
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
PORTFOLIOS_DIR = DATA_DIR / "portfolios"
MICROCAP_DIR = PORTFOLIOS_DIR / "microcap"

FILES_TO_MOVE = [
    "positions.csv", "positions_paper.csv",
    "transactions.csv", "transactions_paper.csv",
    "daily_snapshots.csv", "daily_snapshots_paper.csv",
    "watchlist.jsonl",
    "post_mortems.csv",
    "stale_prices.json",
]


def migrate():
    MICROCAP_DIR.mkdir(parents=True, exist_ok=True)

    # Copy config.json (keep original for backward compat during migration)
    config_src = DATA_DIR / "config.json"
    config_dst = MICROCAP_DIR / "config.json"
    if config_src.exists() and not config_dst.exists():
        shutil.copy2(config_src, config_dst)
        print(f"  Copied config.json → portfolios/microcap/config.json")

    # Move data files
    for fname in FILES_TO_MOVE:
        src = DATA_DIR / fname
        dst = MICROCAP_DIR / fname
        if src.exists() and not dst.exists():
            shutil.move(str(src), str(dst))
            print(f"  Moved {fname} → portfolios/microcap/{fname}")
        elif src.exists() and dst.exists():
            print(f"  Skipped {fname} (already exists in destination)")
        else:
            print(f"  Skipped {fname} (not found)")

    # Create registry
    registry_file = DATA_DIR / "portfolios.json"
    if not registry_file.exists():
        registry = {
            "portfolios": [
                {
                    "id": "microcap",
                    "name": "MicroCap Rebuilder",
                    "universe": "microcap",
                    "created": "2026-02-16",
                    "starting_capital": 50000.0,
                    "active": True,
                }
            ],
            "default_portfolio": "microcap",
        }
        with open(registry_file, "w") as f:
            json.dump(registry, f, indent=2)
        print(f"  Created portfolios.json")

    print("\nMigration complete!")
    print(f"  Portfolio dir: {MICROCAP_DIR}")
    print(f"  Registry: {registry_file}")


if __name__ == "__main__":
    migrate()
```

**Step 4: Run migration**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && python3 scripts/migrate_to_portfolios.py
```

**Step 5: Verify migration worked**

```bash
ls data/portfolios/microcap/
# Should show: config.json, positions.csv (or positions_paper.csv), transactions.csv, etc.
python3 -c "from scripts.portfolio_registry import list_portfolios; print(list_portfolios())"
```

**Step 6: Commit**

```bash
git add scripts/portfolio_registry.py scripts/migrate_to_portfolios.py scripts/data_files.py data/portfolios.json
git commit -m "feat: add portfolio registry, parameterize data paths, migrate microcap data"
```

---

### Task 2: Thread `portfolio_id` Through `portfolio_state.py`

**Files:**
- Modify: `scripts/portfolio_state.py`

**Step 1: Update `load_portfolio_state` signature**

Add `portfolio_id: str | None = None` parameter to `load_portfolio_state()`. Pass it through to all `data_files` calls. The `PortfolioState` dataclass gets a new `portfolio_id: str` field.

Key changes in `portfolio_state.py`:

1. Add `portfolio_id: str = ""` field to the `PortfolioState` dataclass
2. Update `load_portfolio_state(fetch_prices=True, portfolio_id=None)`:
   - Pass `portfolio_id` to `_load_config_from_file(portfolio_id)`
   - Pass `portfolio_id` to `get_positions_file(portfolio_id)`, `get_transactions_file(portfolio_id)`, `get_daily_snapshots_file(portfolio_id)`
   - Pass `portfolio_id` to `is_paper_mode(portfolio_id)`
   - If `portfolio_id` is None, resolve from registry default
   - Set `portfolio_id` on the returned `PortfolioState`
3. Update `save_transaction()`, `save_transactions_batch()`, `save_positions()`, `save_snapshot()`, `remove_position()` — all currently call `get_*_file()` functions. Update them to pass `state.portfolio_id` through.
4. Update stale price tracker path to use portfolio directory

**Step 2: Verify existing behavior unchanged**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && python3 -c "
import sys; sys.path.insert(0, 'scripts')
from portfolio_state import load_portfolio_state
state = load_portfolio_state(fetch_prices=False, portfolio_id='microcap')
print(f'Portfolio: {state.portfolio_id}')
print(f'Cash: \${state.cash:.2f}')
print(f'Positions: {state.num_positions}')
"
```

**Step 3: Commit**

```bash
git add scripts/portfolio_state.py
git commit -m "feat: thread portfolio_id through portfolio_state.py"
```

---

### Task 3: Update CLI Scripts for `--portfolio` Flag

**Files:**
- Modify: `scripts/execute_sells.py`
- Modify: `scripts/pick_from_watchlist.py`
- Modify: `scripts/update_positions.py`
- Modify: `scripts/unified_analysis.py`
- Modify: `scripts/watchlist_manager.py`
- Modify: `run_daily.sh`

**Step 1: Add `--portfolio` argument to each script**

Each script that calls `load_portfolio_state()` needs an `argparse` or simple `sys.argv` handler for `--portfolio`. Pattern:

```python
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio", default=None, help="Portfolio ID")
    # ... existing args ...
    args = parser.parse_args()

    state = load_portfolio_state(fetch_prices=True, portfolio_id=args.portfolio)
    # ... rest of script unchanged ...
```

Apply this pattern to: `execute_sells.py`, `pick_from_watchlist.py`, `update_positions.py`, `unified_analysis.py`, `watchlist_manager.py`.

**Step 2: Create `scripts/list_portfolios.py`**

```python
#!/usr/bin/env python3
"""List active portfolio IDs, one per line. Used by run_daily.sh."""
from portfolio_registry import list_portfolios

for p in list_portfolios(active_only=True):
    print(p.id)
```

**Step 3: Update `run_daily.sh`**

Replace the fixed script calls with a loop:

```bash
# Get all active portfolios
PORTFOLIOS=$(python3 scripts/list_portfolios.py)

for PORTFOLIO in $PORTFOLIOS; do
    echo "═══ Processing portfolio: $PORTFOLIO ═══"

    # Step 0: Stock discovery
    python3 scripts/watchlist_manager.py --update --portfolio "$PORTFOLIO"

    # Step 1-3: Analysis or legacy
    if [ "$UNIFIED_MODE" = "true" ] && [ -n "$ANTHROPIC_API_KEY" ]; then
        python3 scripts/unified_analysis.py --execute --portfolio "$PORTFOLIO"
    else
        python3 scripts/execute_sells.py --portfolio "$PORTFOLIO"
        python3 scripts/pick_from_watchlist.py --portfolio "$PORTFOLIO"
    fi

    # Step 3: Update prices + snapshot
    python3 scripts/update_positions.py --portfolio "$PORTFOLIO"

    # Step 3b: Factor learning
    python3 scripts/factor_learning.py --portfolio "$PORTFOLIO"
done

# Steps 4-5: Reports (aggregate or per-portfolio)
python3 scripts/generate_graph.py --days 30
python3 scripts/generate_report.py
```

**Step 4: Commit**

```bash
git add scripts/execute_sells.py scripts/pick_from_watchlist.py scripts/update_positions.py scripts/unified_analysis.py scripts/watchlist_manager.py scripts/list_portfolios.py run_daily.sh
git commit -m "feat: add --portfolio flag to CLI scripts, loop in run_daily.sh"
```

---

### Task 4: Portfolio-Scoped API Routes

**Files:**
- Modify: `api/main.py`
- Modify: `api/deps.py`
- Modify: `api/routes/state.py`
- Modify: `api/routes/analysis.py`
- Modify: `api/routes/risk.py`
- Modify: `api/routes/performance.py`
- Modify: `api/routes/chat.py`
- Modify: `api/routes/controls.py`
- Modify: `api/routes/discovery.py`
- Create: `api/routes/portfolios.py`

**Step 1: Create portfolio management routes**

Create `api/routes/portfolios.py`:

```python
#!/usr/bin/env python3
"""Portfolio management endpoints."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from portfolio_registry import (
    list_portfolios, load_registry, create_portfolio,
    archive_portfolio, get_default_portfolio_id, UNIVERSE_PRESETS,
)
from portfolio_state import load_portfolio_state
from dataclasses import asdict

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])


class CreatePortfolioRequest(BaseModel):
    id: str
    name: str
    universe: str
    starting_capital: float


@router.get("")
def get_portfolios():
    """List all active portfolios."""
    portfolios = list_portfolios(active_only=True)
    return {
        "portfolios": [asdict(p) for p in portfolios],
        "default_portfolio": get_default_portfolio_id(),
    }


@router.post("")
def create_new_portfolio(req: CreatePortfolioRequest):
    """Create a new portfolio with guided defaults."""
    try:
        meta = create_portfolio(
            portfolio_id=req.id,
            name=req.name,
            universe=req.universe,
            starting_capital=req.starting_capital,
        )
        return {"portfolio": asdict(meta), "message": f"Created portfolio '{req.name}'"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{portfolio_id}")
def delete_portfolio(portfolio_id: str):
    """Archive (soft-delete) a portfolio."""
    archive_portfolio(portfolio_id)
    return {"message": f"Archived portfolio '{portfolio_id}'"}


@router.get("/universes")
def get_universes():
    """List available universe presets."""
    return {k: {"label": v["label"]} for k, v in UNIVERSE_PRESETS.items()}
```

**Step 2: Create aggregate overview route**

Add to `api/routes/portfolios.py`:

```python
@router.get("/overview")
def get_overview():
    """Aggregate view across all portfolios."""
    portfolios = list_portfolios(active_only=True)
    summaries = []
    total_equity = 0
    total_cash = 0
    total_day_pnl = 0

    for p in portfolios:
        try:
            state = load_portfolio_state(fetch_prices=False, portfolio_id=p.id)
            summary = {
                "id": p.id,
                "name": p.name,
                "universe": p.universe,
                "equity": state.total_equity,
                "cash": state.cash,
                "positions_value": state.positions_value,
                "num_positions": state.num_positions,
                "regime": state.regime.value if state.regime else None,
                "paper_mode": state.paper_mode,
            }
            total_equity += state.total_equity
            total_cash += state.cash
            summaries.append(summary)
        except Exception as e:
            summaries.append({
                "id": p.id, "name": p.name, "universe": p.universe,
                "error": str(e),
            })

    return {
        "total_equity": total_equity,
        "total_cash": total_cash,
        "total_day_pnl": total_day_pnl,
        "portfolios": summaries,
    }
```

**Step 3: Add `portfolio_id` path param to all existing routes**

Pattern for each route file — change prefix and add path parameter:

In `api/routes/state.py`, change:
```python
router = APIRouter(prefix="/api", tags=["state"])
```
to:
```python
router = APIRouter(prefix="/api/{portfolio_id}", tags=["state"])
```

And update each endpoint to accept `portfolio_id: str` and pass it to `load_portfolio_state(portfolio_id=portfolio_id)`.

Example for `state.py`:
```python
@router.get("/state")
def get_state(portfolio_id: str):
    state = load_portfolio_state(fetch_prices=False, portfolio_id=portfolio_id)
    return _serialize_state(state)

@router.get("/state/refresh")
def refresh_state(portfolio_id: str):
    state = load_portfolio_state(fetch_prices=True, portfolio_id=portfolio_id)
    # ... rest unchanged, just pass portfolio_id where needed ...
```

Apply the same pattern to:
- `api/routes/analysis.py`: Change `_last_analysis` from a single dict to `_last_analysis: dict[str, dict]` keyed by portfolio_id
- `api/routes/risk.py`: Pass portfolio_id to state loading
- `api/routes/performance.py`: Pass portfolio_id to state loading
- `api/routes/chat.py`: Pass portfolio_id to state and chat context
- `api/routes/controls.py`: Pass portfolio_id to sell/mode/close-all
- `api/routes/discovery.py`: Pass portfolio_id to watchlist manager

**Step 4: Mount new router in `api/main.py`**

```python
from api.routes import portfolios
app.include_router(portfolios.router)
```

**Step 5: Verify API starts**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && source .venv/bin/activate && python3 -c "from api.main import app; print('API loaded OK')"
```

**Step 6: Commit**

```bash
git add api/
git commit -m "feat: portfolio-scoped API routes + portfolio management endpoints"
```

---

### Task 5: Dashboard — Portfolio Store & API Layer

**Files:**
- Modify: `dashboard/src/lib/store.ts`
- Modify: `dashboard/src/lib/api.ts`
- Modify: `dashboard/src/lib/types.ts`

**Step 1: Add portfolio types to `types.ts`**

```typescript
export interface PortfolioMeta {
  id: string;
  name: string;
  universe: string;
  created: string;
  starting_capital: number;
  active: boolean;
}

export interface PortfolioList {
  portfolios: PortfolioMeta[];
  default_portfolio: string;
}

export interface PortfolioSummary {
  id: string;
  name: string;
  universe: string;
  equity: number;
  cash: number;
  positions_value: number;
  num_positions: number;
  regime: string | null;
  paper_mode: boolean;
  error?: string;
}

export interface OverviewData {
  total_equity: number;
  total_cash: number;
  total_day_pnl: number;
  portfolios: PortfolioSummary[];
}

export interface CreatePortfolioRequest {
  id: string;
  name: string;
  universe: string;
  starting_capital: number;
}
```

**Step 2: Add portfolio store to `store.ts`**

```typescript
interface PortfolioStore {
  activePortfolioId: string | "overview";
  setPortfolio: (id: string | "overview") => void;
}

export const usePortfolioStore = create<PortfolioStore>((set) => ({
  activePortfolioId: "overview",
  setPortfolio: (id) => set({ activePortfolioId: id }),
}));
```

**Step 3: Update `api.ts` — parameterize all endpoints**

Change all API functions to accept an optional `portfolioId` parameter and include it in the URL path:

```typescript
// Portfolio management (no portfolio_id prefix)
getPortfolios: () => get<PortfolioList>("/api/portfolios"),
getOverview: () => get<OverviewData>("/api/portfolios/overview"),
createPortfolio: (req: CreatePortfolioRequest) => post<{ portfolio: PortfolioMeta; message: string }>("/api/portfolios", req),
deletePortfolio: (id: string) => fetch(`/api/portfolios/${id}`, { method: "DELETE" }).then(r => r.json()),
getUniverses: () => get<Record<string, { label: string }>>("/api/portfolios/universes"),

// Portfolio-scoped endpoints (require portfolioId)
getState: (portfolioId: string) => get<PortfolioState>(`/api/${portfolioId}/state`),
refreshState: (portfolioId: string) => get<PortfolioState>(`/api/${portfolioId}/state/refresh`),
getRisk: (portfolioId: string) => get<RiskScoreboard>(`/api/${portfolioId}/risk`),
getWarnings: (portfolioId: string) => get<Warning[]>(`/api/${portfolioId}/warnings`),
getPerformance: (portfolioId: string) => get<PerformanceData>(`/api/${portfolioId}/performance`),
getLearning: (portfolioId: string) => get<LearningData>(`/api/${portfolioId}/learning`),
getMommyInsight: (portfolioId: string) => get<MommyInsight>(`/api/${portfolioId}/mommy/insight`),
analyze: (portfolioId: string) => post<AnalysisResult>(`/api/${portfolioId}/analyze`),
execute: (portfolioId: string) => post<Record<string, unknown>>(`/api/${portfolioId}/execute`),
chat: (portfolioId: string, message: string) => post<{ message: string; success: boolean; error: string | null }>(`/api/${portfolioId}/chat`, { message }),
sellPosition: (portfolioId: string, ticker: string) => post<Record<string, unknown>>(`/api/${portfolioId}/sell/${ticker}`),
scan: (portfolioId: string) => post<ScanResult>(`/api/${portfolioId}/scan`),
toggleMode: (portfolioId: string) => post<{ paper_mode: boolean; message: string }>(`/api/${portfolioId}/mode/toggle`),
closeAll: (portfolioId: string) => post<Record<string, unknown>>(`/api/${portfolioId}/close-all`),
updatePrices: (portfolioId: string) => get<PortfolioState>(`/api/${portfolioId}/state/refresh`),
```

**Step 4: Commit**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder/dashboard && git add src/lib/
git commit -m "feat: add portfolio store, types, and portfolio-aware API layer"
```

---

### Task 6: Dashboard — Update All Hooks for Portfolio Awareness

**Files:**
- Modify: `dashboard/src/hooks/usePortfolioState.ts`
- Modify: `dashboard/src/hooks/useRisk.ts`
- Modify: `dashboard/src/hooks/usePerformance.ts`
- Modify: `dashboard/src/hooks/useChartData.ts`
- Modify: `dashboard/src/hooks/useKeyboardShortcuts.ts`
- Create: `dashboard/src/hooks/usePortfolios.ts`

**Step 1: Create `usePortfolios.ts` hook**

```typescript
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { PortfolioList, OverviewData } from "../lib/types";

export function usePortfolios() {
  return useQuery<PortfolioList>({
    queryKey: ["portfolios"],
    queryFn: api.getPortfolios,
    refetchInterval: 60_000,
  });
}

export function useOverview() {
  return useQuery<OverviewData>({
    queryKey: ["overview"],
    queryFn: api.getOverview,
    refetchInterval: 30_000,
  });
}
```

**Step 2: Update all existing hooks to read `activePortfolioId` from store**

Pattern — each hook reads portfolio ID and includes it in queryKey + queryFn:

```typescript
// usePortfolioState.ts
export function usePortfolioState() {
  const portfolioId = usePortfolioStore((s) => s.activePortfolioId);

  return useQuery<PortfolioState>({
    queryKey: ["portfolioState", portfolioId],
    queryFn: () => api.getState(portfolioId),
    refetchInterval: 30_000,
    enabled: portfolioId !== "overview",
  });
}
```

Same pattern for `useRisk`, `useWarnings`, `usePerformance`, `useLearning`, `useChartData`. Add `enabled: portfolioId !== "overview"` to prevent fetching when on overview page.

**Step 3: Update `useKeyboardShortcuts.ts`**

Add portfolio-aware guards — shortcuts only active when viewing a specific portfolio (not overview).

**Step 4: Update `AnalysisStore` in `store.ts`**

Make `runAnalysis` and `runExecute` portfolio-aware:

```typescript
runAnalysis: async () => {
  const portfolioId = usePortfolioStore.getState().activePortfolioId;
  if (portfolioId === "overview") return;
  set({ isAnalyzing: true, error: null });
  try {
    const result = await api.analyze(portfolioId);
    set({ result, lastAnalyzedAt: new Date().toLocaleTimeString() });
  } catch (e) {
    set({ error: (e as Error).message });
  } finally {
    set({ isAnalyzing: false });
  }
},
```

**Step 5: Commit**

```bash
git add dashboard/src/hooks/ dashboard/src/lib/store.ts
git commit -m "feat: portfolio-aware hooks and analysis store"
```

---

### Task 7: Dashboard — Portfolio Switcher & Overview Page

**Files:**
- Create: `dashboard/src/components/PortfolioSwitcher.tsx`
- Create: `dashboard/src/components/OverviewPage.tsx`
- Modify: `dashboard/src/components/TopBar.tsx`
- Modify: `dashboard/src/App.tsx`

**Step 1: Create `PortfolioSwitcher.tsx`**

Dropdown in TopBar showing:
- "Overview" option (aggregate view)
- Divider
- List of portfolio names with universe badges
- "+" button at bottom → opens CreatePortfolioModal

Style: dark dropdown matching cyberpunk theme. Active portfolio highlighted with cyan accent.

**Step 2: Create `CreatePortfolioModal.tsx`**

Modal with:
- Name input (text)
- ID input (auto-generated from name, slug format, editable)
- Universe selector (5 cards with descriptions from presets)
- Starting capital input (number, formatted)
- Create button

**Step 3: Create `OverviewPage.tsx`**

Shown when `activePortfolioId === "overview"`. Contains:
- **Aggregate metrics bar**: Total equity, total cash across all portfolios
- **Portfolio cards grid** (2-3 columns): Each card shows:
  - Name + universe badge
  - Equity (large, monospace)
  - Position count
  - Return % (color-coded)
  - Risk score ring (small)
  - Paper/Live badge
  - Click → `setPortfolio(id)`

**Step 4: Update `TopBar.tsx`**

- Add PortfolioSwitcher component to the left side (after logo, before metrics)
- Metrics, action buttons, etc. only show when viewing a specific portfolio
- When on overview, TopBar shows aggregate metrics only

**Step 5: Update `App.tsx`**

Conditional rendering based on `activePortfolioId`:
- `"overview"` → render OverviewPage (full width, no panels)
- Any portfolio ID → render current four-panel layout (unchanged)

**Step 6: Update all components that call `api.*` functions**

Components like `TopBar` (UpdatePricesButton, ScanButton, EmergencyClose, ModeToggle), `MommyCoPilot`, `ActionsTab`, `PositionDetail` — all need to read `activePortfolioId` from store and pass it to API calls.

**Step 7: Commit**

```bash
git add dashboard/src/
git commit -m "feat: portfolio switcher, overview page, and portfolio-aware components"
```

---

### Task 8: Integration Testing & Polish

**Step 1: Start the dashboard and verify**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder && ./run_dashboard.sh
```

**Step 2: Test checklist**

- [ ] Overview page loads and shows microcap portfolio card
- [ ] Clicking microcap card enters full portfolio view
- [ ] All existing functionality works (positions, analyze, execute, risk, performance, chat)
- [ ] Portfolio switcher dropdown works
- [ ] "+" button opens creation modal
- [ ] Creating a new portfolio (e.g., "allcap", largecap universe, $100k) succeeds
- [ ] New portfolio appears in switcher and overview
- [ ] Switching between portfolios loads correct data
- [ ] Keyboard shortcuts work in portfolio view, disabled in overview
- [ ] API endpoints respond correctly with portfolio_id path param

**Step 3: Fix any issues found**

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: multi-portfolio support — complete implementation"
```

---

## Task Dependency Graph

```
Task 1 (registry + data_files + migration)
  └── Task 2 (portfolio_state.py)
        ├── Task 3 (CLI scripts + run_daily.sh)
        └── Task 4 (API routes)
              └── Task 5 (dashboard types + store + api)
                    └── Task 6 (dashboard hooks)
                          └── Task 7 (UI components)
                                └── Task 8 (integration testing)
```

Tasks 3 and 4 can run in parallel (both depend on Task 2, independent of each other).
Tasks 5-7 are sequential (each builds on the previous).
