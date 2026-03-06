# Sector-Bucketed Watchlist Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the flat global-score watchlist with sector-weight-proportional buckets so each portfolio's watchlist reflects its strategy intent.

**Architecture:** Mode is auto-detected from `discovery.watchlist.sector_weights` in config — when present and non-empty, sector-bucketed mode activates; otherwise existing global sort runs unchanged. Discovery fills each sector bucket independently (top N by score within sector). Enforcement trims per-bucket rather than globally.

**Tech Stack:** Python 3 (scripts), FastAPI (api/), React 19 + TypeScript (dashboard/), pytest for tests.

**Design doc:** `docs/plans/2026-03-06-sector-bucketed-watchlist-design.md`

---

## Setup

Before starting, create the test infrastructure:

```bash
mkdir -p /Users/gregmclaughlin/MicroCapRebuilder/tests
```

Create `tests/conftest.py`:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
```

Run tests from the project root:
```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
pytest tests/ -v
```

---

## Task 1: portfolio_registry.py — preset defaults + sector_weights param

**Files:**
- Modify: `scripts/portfolio_registry.py`
- Test: `tests/test_task1_registry.py`

### Step 1: Write the failing test

Create `tests/test_task1_registry.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from portfolio_registry import UNIVERSE_PRESETS


def test_total_watchlist_slots_in_presets():
    assert UNIVERSE_PRESETS["smallcap"]["total_watchlist_slots"] == 150
    assert UNIVERSE_PRESETS["midcap"]["total_watchlist_slots"] == 180
    assert UNIVERSE_PRESETS["largecap"]["total_watchlist_slots"] == 200
    assert UNIVERSE_PRESETS["allcap"]["total_watchlist_slots"] == 250
    # microcap stays flat — no bucketing, no slot count needed
    assert "total_watchlist_slots" not in UNIVERSE_PRESETS["microcap"]


def test_create_portfolio_accepts_sector_weights():
    """create_portfolio() signature must accept sector_weights param."""
    import inspect
    from portfolio_registry import create_portfolio
    sig = inspect.signature(create_portfolio)
    assert "sector_weights" in sig.parameters
```

### Step 2: Run to verify it fails

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
pytest tests/test_task1_registry.py -v
```
Expected: FAIL — `KeyError: 'total_watchlist_slots'` and missing param.

### Step 3: Add `total_watchlist_slots` to presets

In `scripts/portfolio_registry.py`, add `"total_watchlist_slots"` to each relevant preset.

Find the `"smallcap"` preset block (around line 46) and add the key:
```python
"smallcap": {
    "label": "Small-Cap ($300M–$2B)",
    "total_watchlist_slots": 150,   # ADD THIS
    ...
},
```

Do the same for `midcap` (180), `largecap` (200), `allcap` (250). **Do not add to `microcap`** — it stays on global mode.

### Step 4: Add `sector_weights` param to `create_portfolio()`

Find the `create_portfolio()` function signature (around line 355):
```python
def create_portfolio(
    portfolio_id: str,
    name: str,
    universe: str,
    starting_capital: float,
    sectors: list[str] = None,
    trading_style: str = None,
    ai_config: dict = None,
) -> PortfolioMeta:
```

Change to:
```python
def create_portfolio(
    portfolio_id: str,
    name: str,
    universe: str,
    starting_capital: float,
    sectors: list[str] = None,
    trading_style: str = None,
    ai_config: dict = None,
    sector_weights: dict = None,
) -> PortfolioMeta:
```

### Step 5: Write sector_weights into config inside `create_portfolio()`

Find the section after Layer 3 (sector focus) in `create_portfolio()`, just before Layer 4 (AI overrides). Add:

```python
    # --- Sector watchlist config ---
    if "watchlist" not in config["discovery"]:
        config["discovery"]["watchlist"] = {}
    config["discovery"]["watchlist"]["total_watchlist_slots"] = preset.get(
        "total_watchlist_slots", config["discovery"].get("watchlist", {}).get("max_tickers", 150)
    )
    if sector_weights:
        config["discovery"]["watchlist"]["sector_weights"] = dict(sector_weights)
    else:
        config["discovery"]["watchlist"].pop("sector_weights", None)
```

Also in **Layer 4 (AI overrides)**, add support for AI-generated sector_weights (after the existing `if "sectors" in ai_config:` block):
```python
        if "sector_weights" in ai_config:
            if "watchlist" not in config["discovery"]:
                config["discovery"]["watchlist"] = {}
            config["discovery"]["watchlist"]["sector_weights"] = ai_config["sector_weights"]
```

### Step 6: Run tests to verify they pass

```bash
pytest tests/test_task1_registry.py -v
```
Expected: PASS both tests.

### Step 7: Commit

```bash
git add scripts/portfolio_registry.py tests/test_task1_registry.py tests/conftest.py
git commit -m "feat: add total_watchlist_slots to presets and sector_weights param to create_portfolio"
```

---

## Task 2: strategy_generator.py — AI outputs sector_weights

**Files:**
- Modify: `scripts/strategy_generator.py`
- Test: `tests/test_task2_strategy_generator.py`

### Step 1: Write the failing test

Create `tests/test_task2_strategy_generator.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from strategy_generator import GeneratedStrategy, _normalize_sector_weights


def test_generated_strategy_has_sector_weights_field():
    import inspect, dataclasses
    fields = {f.name for f in dataclasses.fields(GeneratedStrategy)}
    assert "sector_weights" in fields


def test_normalize_sector_weights_sums_correctly():
    weights = {"Technology": 60, "Healthcare": 40}
    result = _normalize_sector_weights(weights, ["Technology", "Healthcare"])
    assert result == {"Technology": 60, "Healthcare": 40}


def test_normalize_sector_weights_fills_missing_sectors():
    weights = {"Technology": 100}
    result = _normalize_sector_weights(weights, ["Technology", "Healthcare"])
    assert "Healthcare" in result
    assert result["Healthcare"] > 0


def test_normalize_sector_weights_handles_empty():
    result = _normalize_sector_weights({}, ["Technology", "Healthcare"])
    # Equal weights when nothing specified
    assert result["Technology"] == result["Healthcare"]
```

### Step 2: Run to verify it fails

```bash
pytest tests/test_task2_strategy_generator.py -v
```
Expected: FAIL — `sector_weights` not in `GeneratedStrategy`, `_normalize_sector_weights` not found.

### Step 3: Add `sector_weights` to `GeneratedStrategy` dataclass

In `scripts/strategy_generator.py`, find the `GeneratedStrategy` dataclass and add the field:

```python
@dataclass
class GeneratedStrategy:
    sectors: list[str]
    sector_weights: dict[str, int]   # ADD THIS — maps sector → relative weight
    trading_style: Optional[str]
    scoring_weights: dict[str, float]
    stop_loss_pct: float
    risk_per_trade_pct: float
    max_position_pct: float
    scan_types: dict[str, bool]
    etf_sources: list[str]
    strategy_name: str
    rationale: str
    prompt: str
```

### Step 4: Add `_normalize_sector_weights()` helper

Add this function after `_validate_weights()` (around line 104):

```python
def _normalize_sector_weights(raw: dict, sectors: list[str]) -> dict[str, int]:
    """Ensure every sector has a weight; equal weight for any missing sector.

    Returns integer weights (not normalized to 100 — proportional is fine).
    """
    result = {s: int(raw.get(s, 0)) for s in sectors}
    # Fill zeros with the average of non-zero weights, or 10 as fallback
    non_zero = [v for v in result.values() if v > 0]
    default = int(sum(non_zero) / len(non_zero)) if non_zero else 10
    for s in sectors:
        if result[s] == 0:
            result[s] = default
    return result
```

### Step 5: Update `STRATEGY_SYSTEM_PROMPT` to request sector_weights

Find the JSON schema block in `STRATEGY_SYSTEM_PROMPT` and add the `sector_weights` field after `"sectors"`:

```python
STRATEGY_SYSTEM_PROMPT = """You are GScott's strategy architect. Given a user's description of their desired trading strategy, generate a portfolio configuration.

You MUST return ONLY valid JSON with these exact fields:
{
  "strategy_name": "Short descriptive name for this strategy",
  "sectors": ["list of GICS sectors to focus on"],
  "sector_weights": {"SectorName": integer_weight, ...},
  "trading_style": "aggressive_momentum" | "balanced" | "conservative_value" | "mean_reversion" | null,
  ...rest unchanged...
}

Rules:
...existing rules...
- sector_weights must include every sector listed in "sectors". Use proportional integers (e.g., Technology: 40, Healthcare: 25). Higher = more watchlist slots. If the strategy emphasizes one sector, weight it higher.
"""
```

### Step 6: Extract `sector_weights` in `generate_strategy()` and return it

In `generate_strategy()`, after validating `sectors` (around line 155), add:

```python
    # Extract and normalize sector weights
    raw_weights = data.get("sector_weights", {})
    sector_weights = _normalize_sector_weights(raw_weights, sectors)
```

Update the `return GeneratedStrategy(...)` call to include `sector_weights=sector_weights`:

```python
    return GeneratedStrategy(
        sectors=sectors,
        sector_weights=sector_weights,    # ADD THIS
        trading_style=data.get("trading_style"),
        ...rest unchanged...
    )
```

### Step 7: Run tests to verify they pass

```bash
pytest tests/test_task2_strategy_generator.py -v
```
Expected: PASS all 4 tests.

### Step 8: Commit

```bash
git add scripts/strategy_generator.py tests/test_task2_strategy_generator.py
git commit -m "feat: add sector_weights to GeneratedStrategy and AI prompt"
```

---

## Task 3: api/routes/portfolios.py — thread sector_weights through API

**Files:**
- Modify: `api/routes/portfolios.py`
- Test: `tests/test_task3_api_portfolio.py`

### Step 1: Write the failing test

Create `tests/test_task3_api_portfolio.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.routes.portfolios import CreatePortfolioRequest
import inspect


def test_create_portfolio_request_has_sector_weights():
    import dataclasses
    # Pydantic model fields
    fields = CreatePortfolioRequest.model_fields
    assert "sector_weights" in fields


def test_create_portfolio_request_sector_weights_optional():
    req = CreatePortfolioRequest(
        id="test", name="Test", universe="largecap", starting_capital=10000
    )
    assert req.sector_weights is None
```

### Step 2: Run to verify it fails

```bash
pytest tests/test_task3_api_portfolio.py -v
```
Expected: FAIL — `sector_weights` not in `CreatePortfolioRequest`.

### Step 3: Add `sector_weights` to `CreatePortfolioRequest`

In `api/routes/portfolios.py`, find `CreatePortfolioRequest` (around line 41):

```python
class CreatePortfolioRequest(BaseModel):
    id: str
    name: str
    universe: str
    starting_capital: float
    sectors: list[str] | None = None
    trading_style: str | None = None
    ai_config: dict | None = None
    sector_weights: dict[str, int] | None = None   # ADD THIS
```

### Step 4: Pass `sector_weights` to `create_portfolio()`

In the `create_new_portfolio()` route handler (around line 64):

```python
        meta = create_portfolio(
            portfolio_id=req.id, name=req.name,
            universe=req.universe, starting_capital=req.starting_capital,
            sectors=req.sectors, trading_style=req.trading_style,
            ai_config=req.ai_config,
            sector_weights=req.sector_weights,   # ADD THIS
        )
```

### Step 5: Return `sector_weights` from `generate_strategy_endpoint`

In `generate_strategy_endpoint()` (around line 86), the return dict currently includes `sectors`, `trading_style`, etc. Add `sector_weights`:

```python
        return {
            "sectors": strategy.sectors,
            "sector_weights": strategy.sector_weights,   # ADD THIS
            "trading_style": strategy.trading_style,
            ...rest unchanged...
        }
```

### Step 6: Run tests to verify they pass

```bash
pytest tests/test_task3_api_portfolio.py -v
```
Expected: PASS both tests.

### Step 7: Commit

```bash
git add api/routes/portfolios.py tests/test_task3_api_portfolio.py
git commit -m "feat: thread sector_weights through portfolios API create and generate-strategy"
```

---

## Task 4: stock_discovery.py — bucketed selection after scan

**Files:**
- Modify: `scripts/stock_discovery.py`
- Test: `tests/test_task4_bucketed_selection.py`

### Step 1: Write the failing test

Create `tests/test_task4_bucketed_selection.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from stock_discovery import StockDiscovery, DiscoveredStock
from datetime import date


def _make_candidate(ticker: str, sector: str, score: float) -> DiscoveredStock:
    return DiscoveredStock(
        ticker=ticker, source="MOMENTUM_BREAKOUT", discovery_score=score,
        sector=sector, market_cap_m=1000.0, avg_volume=500000,
        current_price=50.0, momentum_20d=5.0, rsi_14=55.0,
        volume_ratio=1.5, near_52wk_high_pct=95.0,
        discovered_date=date.today().isoformat(), notes="",
    )


def _make_discovery() -> StockDiscovery:
    d = object.__new__(StockDiscovery)
    return d


def test_select_by_buckets_respects_slot_limits():
    discovery = _make_discovery()
    candidates = [
        _make_candidate("AAPL", "Technology", 90),
        _make_candidate("MSFT", "Technology", 85),
        _make_candidate("GOOG", "Technology", 80),  # should be cut
        _make_candidate("JNJ", "Healthcare", 88),
        _make_candidate("PFE", "Healthcare", 75),
    ]
    result = discovery._select_by_buckets(candidates, {"Technology": 50, "Healthcare": 50}, total_slots=4)
    tickers = {r.ticker for r in result}
    assert "AAPL" in tickers   # top Tech
    assert "MSFT" in tickers   # 2nd Tech
    assert "GOOG" not in tickers  # 3rd Tech, cut
    assert "JNJ" in tickers   # top Healthcare
    assert "PFE" in tickers   # 2nd Healthcare


def test_select_by_buckets_proportional_weighting():
    discovery = _make_discovery()
    candidates = [_make_candidate(f"T{i}", "Technology", 90 - i) for i in range(6)]
    candidates += [_make_candidate(f"H{i}", "Healthcare", 80 - i) for i in range(4)]
    # Tech 75%, Healthcare 25% → 9 Tech slots, 3 Healthcare slots out of 12
    result = discovery._select_by_buckets(
        candidates, {"Technology": 75, "Healthcare": 25}, total_slots=12
    )
    tech_count = sum(1 for r in result if r.sector == "Technology")
    health_count = sum(1 for r in result if r.sector == "Healthcare")
    assert tech_count == 9
    assert health_count == 3


def test_select_by_buckets_leaves_empty_slots_when_sector_sparse():
    discovery = _make_discovery()
    candidates = [
        _make_candidate("AAPL", "Technology", 90),
        # Healthcare has 0 candidates
    ]
    result = discovery._select_by_buckets(
        candidates, {"Technology": 50, "Healthcare": 50}, total_slots=10
    )
    # Only 1 Tech candidate fills 1 slot; Healthcare stays empty
    assert len(result) == 1
    assert result[0].ticker == "AAPL"


def test_select_by_buckets_fuzzy_sector_match():
    """yfinance returns 'Communication Services'; sector_weights key is 'Communication'."""
    discovery = _make_discovery()
    candidates = [_make_candidate("META", "Communication Services", 85)]
    result = discovery._select_by_buckets(
        candidates, {"Communication": 100}, total_slots=5
    )
    assert len(result) == 1
    assert result[0].ticker == "META"
```

### Step 2: Run to verify it fails

```bash
pytest tests/test_task4_bucketed_selection.py -v
```
Expected: FAIL — `_select_by_buckets` not found.

### Step 3: Add `_select_by_buckets()` to `StockDiscovery`

In `scripts/stock_discovery.py`, add this method to the `StockDiscovery` class. Good place: just before `scan_momentum_breakouts()` (around line 415):

```python
    def _select_by_buckets(
        self,
        candidates: List[DiscoveredStock],
        sector_weights: Dict[str, int],
        total_slots: int,
    ) -> List[DiscoveredStock]:
        """Select top-scoring candidates per sector bucket based on weight ratios.

        Args:
            candidates: All passing candidates (already deduplicated).
            sector_weights: Maps sector name → relative integer weight.
            total_slots: Total watchlist slots to fill.

        Returns:
            Selected candidates, at most total_slots total.
        """
        # Compute per-bucket slot counts (proportional to weights)
        total_weight = sum(sector_weights.values()) or 1
        sorted_sectors = sorted(sector_weights.items(), key=lambda x: x[1], reverse=True)
        bucket_sizes: Dict[str, int] = {}
        allocated = 0
        for sector, weight in sorted_sectors:
            size = round(total_slots * weight / total_weight)
            bucket_sizes[sector] = size
            allocated += size
        # Fix rounding: remainder goes to highest-weight sector
        diff = total_slots - allocated
        if diff != 0 and sorted_sectors:
            bucket_sizes[sorted_sectors[0][0]] += diff

        # Group candidates into buckets using fuzzy sector matching
        by_bucket: Dict[str, List[DiscoveredStock]] = {s: [] for s in sector_weights}
        for candidate in candidates:
            for bucket_key in sector_weights:
                if _sector_matches(candidate.sector, [bucket_key]):
                    by_bucket[bucket_key].append(candidate)
                    break  # assign to first matching bucket only

        # Fill each bucket: top N by discovery_score
        selected: List[DiscoveredStock] = []
        for bucket_key, limit in bucket_sizes.items():
            bucket = by_bucket[bucket_key]
            bucket.sort(key=lambda x: x.discovery_score, reverse=True)
            selected.extend(bucket[:limit])

        return selected
```

### Step 4: Wire bucketed selection into `run_all_scans()`

In `run_all_scans()`, find the final block starting at "Deduplicate by ticker" (around line 786). After the deduplication and sort, add the bucket selection:

Current code ends with:
```python
        # Sort by discovery score
        result = list(ticker_map.values())
        result.sort(key=lambda x: x.discovery_score, reverse=True)

        total_elapsed = time.time() - scan_start
        print(f"\nTotal unique candidates: {len(result)} (scan completed in {total_elapsed:.1f}s)")
        return result
```

Replace with:
```python
        # Sort by discovery score (global sort — used as-is in global mode,
        # or as pre-sort before bucket selection in bucketed mode)
        result = list(ticker_map.values())
        result.sort(key=lambda x: x.discovery_score, reverse=True)

        # Bucketed mode: select top-N per sector bucket
        watchlist_cfg = self.discovery_config.get("watchlist", {})
        sector_weights = watchlist_cfg.get("sector_weights", {})
        if sector_weights:
            total_slots = watchlist_cfg.get(
                "total_watchlist_slots",
                watchlist_cfg.get("max_tickers", 150),
            )
            result = self._select_by_buckets(result, sector_weights, total_slots)
            print(f"  Bucketed selection: {len(result)} candidates across {len(sector_weights)} sectors")

        total_elapsed = time.time() - scan_start
        print(f"\nTotal unique candidates: {len(result)} (scan completed in {total_elapsed:.1f}s)")
        return result
```

**Note:** `self.discovery_config` in `StockDiscovery` is `config.get("discovery", {})` — check what key it's under. Look at `StockDiscovery.__init__` to confirm:

```bash
grep -n "self.discovery_config\s*=" /Users/gregmclaughlin/MicroCapRebuilder/scripts/stock_discovery.py | head -5
```

If it's `config.get("discovery", {})`, then `self.discovery_config.get("watchlist", {})` is correct.

### Step 5: Run tests to verify they pass

```bash
pytest tests/test_task4_bucketed_selection.py -v
```
Expected: PASS all 4 tests.

### Step 6: Commit

```bash
git add scripts/stock_discovery.py tests/test_task4_bucketed_selection.py
git commit -m "feat: add sector-bucketed candidate selection to stock_discovery"
```

---

## Task 5: watchlist_manager.py — enforce_bucket_sizes + update_watchlist

**Files:**
- Modify: `scripts/watchlist_manager.py`
- Test: `tests/test_task5_watchlist_buckets.py`

### Step 1: Write the failing test

Create `tests/test_task5_watchlist_buckets.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from watchlist_manager import WatchlistManager


def _make_manager(sector_weights=None, total_slots=100):
    m = object.__new__(WatchlistManager)
    m.sector_weights = sector_weights or {}
    m.total_watchlist_slots = total_slots
    m.max_tickers = 150
    return m


def test_is_bucketed_mode_with_weights():
    m = _make_manager({"Technology": 60, "Healthcare": 40})
    assert m._is_bucketed_mode() is True


def test_is_bucketed_mode_without_weights():
    m = _make_manager()
    assert m._is_bucketed_mode() is False


def test_compute_bucket_sizes_proportional():
    m = _make_manager({"Technology": 60, "Healthcare": 40}, total_slots=100)
    sizes = m._compute_bucket_sizes()
    assert sizes["Technology"] == 60
    assert sizes["Healthcare"] == 40
    assert sum(sizes.values()) == 100


def test_compute_bucket_sizes_rounding_sums_correctly():
    # 3 sectors with odd total — rounding must still sum to total_slots
    m = _make_manager({"Technology": 33, "Healthcare": 33, "Industrials": 34}, total_slots=100)
    sizes = m._compute_bucket_sizes()
    assert sum(sizes.values()) == 100


def test_compute_bucket_sizes_unequal_weights():
    m = _make_manager({"Technology": 75, "Healthcare": 25}, total_slots=200)
    sizes = m._compute_bucket_sizes()
    assert sizes["Technology"] == 150
    assert sizes["Healthcare"] == 50
    assert sum(sizes.values()) == 200
```

### Step 2: Run to verify it fails

```bash
pytest tests/test_task5_watchlist_buckets.py -v
```
Expected: FAIL — `_is_bucketed_mode`, `_compute_bucket_sizes` not found.

### Step 3: Add local `_sector_matches` helper to `watchlist_manager.py`

At the top of `scripts/watchlist_manager.py`, after the imports, add:

```python
def _sector_matches(yf_sector: str, filter_sectors: list) -> bool:
    """Fuzzy sector match: handles yfinance naming mismatches.
    Returns True if the yfinance sector contains any filter string or vice versa.
    Mirrors the same helper in stock_discovery.py to avoid circular imports.
    """
    yf_lower = yf_sector.lower()
    return any(
        f.lower() in yf_lower or yf_lower in f.lower()
        for f in filter_sectors
    )
```

### Step 4: Add `sector_weights` and `total_watchlist_slots` to `WatchlistManager.__init__()`

Find `__init__` (around line 81) and add after `self.max_tickers`:

```python
        self.sector_weights = self.discovery_config.get("sector_weights", {})
        self.total_watchlist_slots = self.discovery_config.get(
            "total_watchlist_slots", self.max_tickers
        )
```

### Step 5: Add `_is_bucketed_mode()` and `_compute_bucket_sizes()` methods

Add these methods to `WatchlistManager` after `get_underrepresented_sectors()` (around line 642):

```python
    def _is_bucketed_mode(self) -> bool:
        """True when sector_weights config is present and non-empty."""
        return bool(self.sector_weights)

    def _compute_bucket_sizes(self) -> Dict[str, int]:
        """Compute per-sector slot limits proportional to sector_weights.

        Rounding correction ensures sum == total_watchlist_slots exactly.
        """
        total_weight = sum(self.sector_weights.values()) or 1
        total = self.total_watchlist_slots
        sorted_sectors = sorted(
            self.sector_weights.items(), key=lambda x: x[1], reverse=True
        )
        bucket_sizes: Dict[str, int] = {}
        allocated = 0
        for sector, weight in sorted_sectors:
            size = round(total * weight / total_weight)
            bucket_sizes[sector] = size
            allocated += size
        # Rounding correction: add/subtract from highest-weight sector
        diff = total - allocated
        if diff != 0 and sorted_sectors:
            bucket_sizes[sorted_sectors[0][0]] += diff
        return bucket_sizes
```

### Step 6: Add `enforce_bucket_sizes()` method

Add after `_compute_bucket_sizes()`:

```python
    def enforce_bucket_sizes(self) -> int:
        """Enforce per-sector slot limits when in bucketed mode.

        In global mode, delegates to enforce_max_size() (unchanged behavior).

        Returns:
            Number of tickers removed.
        """
        if not self._is_bucketed_mode():
            return self.enforce_max_size()

        entries = self._load_watchlist()
        core_tickers = self._load_core_watchlist()
        bucket_sizes = self._compute_bucket_sizes()

        to_remove: Set[str] = set()
        for sector, limit in bucket_sizes.items():
            sector_entries = [
                e for e in entries
                if e.status == "ACTIVE" and _sector_matches(e.sector, [sector])
            ]
            sector_entries.sort(key=lambda x: x.discovery_score, reverse=True)
            for entry in sector_entries[limit:]:
                if entry.ticker not in core_tickers:
                    to_remove.add(entry.ticker)

        if to_remove:
            new_entries = [e for e in entries if e.ticker not in to_remove]
            self._save_watchlist(new_entries)

        return len(to_remove)
```

### Step 7: Update `update_watchlist()` to use new methods

In `update_watchlist()` (around line 377), replace the existing end of the pipeline:

Old:
```python
        # Balance sectors
        stats["sector_balanced"] = self.balance_sectors()

        stats["removed"] += self.enforce_max_size()
```

New:
```python
        # Balance sectors — skip in bucketed mode (bucket sizes already enforce distribution)
        if not self._is_bucketed_mode():
            stats["sector_balanced"] = self.balance_sectors()

        # Enforce size limits (per-bucket in bucketed mode, global in flat mode)
        stats["removed"] += self.enforce_bucket_sizes()
```

### Step 8: Run tests to verify they pass

```bash
pytest tests/test_task5_watchlist_buckets.py -v
```
Expected: PASS all 5 tests.

### Step 9: Run full test suite to check nothing broke

```bash
pytest tests/ -v
```
Expected: all tests pass.

### Step 10: Commit

```bash
git add scripts/watchlist_manager.py tests/test_task5_watchlist_buckets.py
git commit -m "feat: add enforce_bucket_sizes and sector-bucketed update_watchlist"
```

---

## Task 6: CreatePortfolioModal.tsx — Sector Weights step

**Files:**
- Modify: `dashboard/src/components/CreatePortfolioModal.tsx`

No automated tests for this task — verify manually by running the dashboard.

### Step 1: Read the current modal file

```bash
cat /Users/gregmclaughlin/MicroCapRebuilder/dashboard/src/components/CreatePortfolioModal.tsx
```

Understand the current step structure before editing.

### Step 2: Add Sector Weights step to wizard steps array

Find:
```typescript
const WIZARD_STEPS = ["Name & Capital", "Cap Size", "Sectors", "Trading Style", "Review"];
```

Change to:
```typescript
const WIZARD_STEPS = ["Name & Capital", "Cap Size", "Sectors", "Sector Weights", "Trading Style", "Review"];
```

### Step 3: Add `sectorWeights` state and sync with sectors

After the existing `const [sectors, setSectors] = useState<string[]>([...ALL_SECTORS]);` (around line 94), add:

```typescript
const [sectorWeights, setSectorWeights] = useState<Record<string, number>>({});

// Sync weights when sectors change: equal weight for all selected sectors
useEffect(() => {
  if (sectors.length === 0 || sectors.length === ALL_SECTORS.length) {
    setSectorWeights({});
    return;
  }
  const equal = Math.round(100 / sectors.length);
  const weights: Record<string, number> = {};
  sectors.forEach((s, i) => {
    // Assign remainder to first sector so sum == 100
    weights[s] = i === 0 ? 100 - equal * (sectors.length - 1) : equal;
  });
  setSectorWeights(weights);
}, [sectors]);
```

Add the `useEffect` import if not already imported:
```typescript
import { useState, useEffect, useRef } from "react";
```

### Step 4: Add `renderSectorWeightsStep()` function

Add this render function after `renderSectorStep()`:

```typescript
function renderSectorWeightsStep() {
  const total = Object.values(sectorWeights).reduce((a, b) => a + b, 0);
  const isAllSectors = sectors.length === ALL_SECTORS.length;

  if (isAllSectors) {
    return (
      <div className="text-center text-zinc-400 py-8">
        <p className="text-sm">No sector filter — using global score sort.</p>
        <p className="text-xs mt-1 text-zinc-500">Sector weights only apply when specific sectors are selected.</p>
      </div>
    );
  }

  function updateWeight(sector: string, value: string) {
    const num = Math.max(1, Math.min(999, parseInt(value) || 1));
    setSectorWeights((prev) => ({ ...prev, [sector]: num }));
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-zinc-400 mb-4">
        Set relative weight for each sector. Higher = more watchlist slots. Values are proportional — they don't need to sum to 100.
      </p>
      {sectors.map((sector) => {
        const weight = sectorWeights[sector] ?? 10;
        const pct = total > 0 ? Math.round((weight / total) * 100) : 0;
        return (
          <div key={sector} className="flex items-center gap-3">
            <span className="text-sm text-zinc-300 w-44 shrink-0">{sector}</span>
            <input
              type="number"
              min={1}
              max={999}
              value={weight}
              onChange={(e) => updateWeight(sector, e.target.value)}
              className="w-20 bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-sm text-white text-right"
            />
            <span className="text-xs text-zinc-500 w-12">{pct}%</span>
            <div className="flex-1 bg-zinc-800 rounded-full h-1.5">
              <div
                className="bg-blue-500 h-1.5 rounded-full transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
      <p className="text-xs text-zinc-600 mt-2">Total relative weight: {total}</p>
    </div>
  );
}
```

### Step 5: Add the new step to `renderCurrentStep()`

Find `renderCurrentStep()` (around line 549):

```typescript
function renderCurrentStep() {
  if (step === 1) return renderNameStep();
  if (step === 2) return renderUniverseStep();
  if (mode === "wizard") {
    if (step === 3) return renderSectorStep();
    if (step === 4) return renderTradingStyleStep();   // was step 4, now step 5
    if (step === 5) return renderWizardReview();        // was step 5, now step 6
  }
  ...
}
```

Update wizard step routing:
```typescript
function renderCurrentStep() {
  if (step === 1) return renderNameStep();
  if (step === 2) return renderUniverseStep();
  if (mode === "wizard") {
    if (step === 3) return renderSectorStep();
    if (step === 4) return renderSectorWeightsStep();  // NEW
    if (step === 5) return renderTradingStyleStep();
    if (step === 6) return renderWizardReview();
  }
  if (mode === "ai") {
    if (step === 3) return renderAiPromptStep();
    if (step === 4) return renderAiReview();
  }
}
```

### Step 6: Include `sector_weights` in the submit payload

Find the wizard submit payload (around line 197, in `handleSubmit()` or `handleCreate()`):

```typescript
  if (mode === "wizard") {
    payload = {
      ...
      sectors: sectors.length === ALL_SECTORS.length ? undefined : sectors,
      sector_weights: (sectors.length === ALL_SECTORS.length || Object.keys(sectorWeights).length === 0)
        ? undefined
        : sectorWeights,
      ...
    };
  }
```

For the AI mode, `generatedStrategy` must include `sector_weights` from the API response. Find where `generatedStrategy` state is set after the generate-strategy API call and confirm `sector_weights` is included (it will be, since Task 3 added it to the response).

In the AI submit payload, add:
```typescript
      ai_config: {
        ...existingAiConfig,
        sector_weights: generatedStrategy?.sector_weights,
      },
```

### Step 7: Verify manually

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate && uvicorn api.main:app --host 0.0.0.0 --port 8001 &
cd dashboard && npm run dev
```

Open `http://localhost:5173`. Click "New Portfolio" and walk through the wizard:
1. Enter name/capital → Next
2. Select cap size → Next
3. Select a subset of sectors (e.g., Technology + Healthcare + Industrials) → Next
4. ✅ Should see the new "Sector Weights" step with sliders and a progress bar per sector
5. Adjust weights → Next
6. Select trading style → Next
7. Review → Create

Check `data/portfolios/{new-id}/config.json` — should contain:
```json
"watchlist": {
  "total_watchlist_slots": 200,
  "sector_weights": { "Technology": 40, "Healthcare": 30, "Industrials": 30 }
}
```

Also test AI mode: describe a strategy, generate → should see sector_weights in review card.

### Step 8: Commit

```bash
git add dashboard/src/components/CreatePortfolioModal.tsx
git commit -m "feat: add Sector Weights step to CreatePortfolioModal wizard"
```

---

## Final: Run all tests + push

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
pytest tests/ -v
```
Expected: all tests pass.

```bash
git push
```
