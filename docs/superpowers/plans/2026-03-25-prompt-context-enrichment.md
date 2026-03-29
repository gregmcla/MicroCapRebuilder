# Prompt Context Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 5 rich context blocks to Claude's AI allocation prompt (portfolio performance, deterioration alerts, position age, cash idle time, factor intelligence) — preceded by 3 surgical bug fixes that are prerequisites.

**Architecture:** Three pre-work bug fixes make data sourcing correct for multi-portfolio use. Then `_run_ai_driven_analysis` gathers the new data, bundles it into a `prompt_extras` dict, and passes it through `run_ai_allocation` → `_build_allocation_prompt` where 5 new blocks are rendered. All data gathering wrapped in try/except so any failure silently omits the block.

**Tech Stack:** Python 3, pandas, existing project modules (`trade_analyzer`, `early_warning`, `analytics`, `factor_learning`, `portfolio_state`)

---

## Files Changed

| File | Change |
|---|---|
| `scripts/trade_analyzer.py` | Bug A: Add `__init__(self, portfolio_id=None)`, thread into `load_transactions()` |
| `scripts/early_warning.py` | Bug B: Pass `portfolio_id` to `TradeAnalyzer()` in `EarlyWarningSystem.__init__` |
| `scripts/analytics.py` | Bug C: Read benchmark from `self.config` in `fetch_benchmark_data()` |
| `scripts/unified_analysis.py` | Gather prompt_extras in `_run_ai_driven_analysis`, pass to `run_ai_allocation` |
| `scripts/ai_allocator.py` | Add `prompt_extras` param; render 5 new context blocks in prompt |
| `tests/test_prompt_context_enrichment.py` | All tests for this feature |

---

## Task 1: Fix TradeAnalyzer portfolio_id (Bug A)

**Files:**
- Modify: `scripts/trade_analyzer.py:60-66`
- Test: `tests/test_prompt_context_enrichment.py`

**Background:** `TradeAnalyzer` has no `__init__` — so `load_transactions()` calls `load_portfolio_state(fetch_prices=False)` without `portfolio_id`, silently reading the wrong portfolio's transactions for any portfolio other than the default. This corrupts the trade stats used in the portfolio performance block.

- [ ] **Step 1: Write the failing test**

Create `tests/test_prompt_context_enrichment.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import inspect
from unittest.mock import patch, MagicMock


# ─── Task 1: TradeAnalyzer portfolio_id ────────────────────────────────────────

def test_trade_analyzer_accepts_portfolio_id():
    """TradeAnalyzer.__init__ must accept portfolio_id and store it."""
    from trade_analyzer import TradeAnalyzer
    ta = TradeAnalyzer(portfolio_id="microcap")
    assert ta.portfolio_id == "microcap"


def test_trade_analyzer_no_arg_defaults_to_none():
    from trade_analyzer import TradeAnalyzer
    ta = TradeAnalyzer()
    assert ta.portfolio_id is None


def test_trade_analyzer_load_transactions_uses_portfolio_id():
    """load_transactions() must pass portfolio_id to load_portfolio_state."""
    from trade_analyzer import TradeAnalyzer
    import pandas as pd
    mock_state = MagicMock()
    mock_state.transactions = pd.DataFrame()
    with patch("trade_analyzer.load_portfolio_state", return_value=mock_state) as mock_load:
        ta = TradeAnalyzer(portfolio_id="my-portfolio")
        ta.load_transactions()
        mock_load.assert_called_once_with(fetch_prices=False, portfolio_id="my-portfolio")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
pytest tests/test_prompt_context_enrichment.py::test_trade_analyzer_accepts_portfolio_id -v
```
Expected: FAIL — `TradeAnalyzer() takes no arguments` or `has no attribute 'portfolio_id'`

- [ ] **Step 3: Add `__init__` to TradeAnalyzer**

In `scripts/trade_analyzer.py`, insert after line 60 (`class TradeAnalyzer:`):

```python
class TradeAnalyzer:
    """Analyze trade performance."""

    def __init__(self, portfolio_id: str = None):
        self.portfolio_id = portfolio_id

    def load_transactions(self) -> pd.DataFrame:
        """Load all transactions."""
        state = load_portfolio_state(fetch_prices=False, portfolio_id=self.portfolio_id)
        return state.transactions
```

(Replace the existing `load_transactions` which lacks `__init__` and calls `load_portfolio_state(fetch_prices=False)` without portfolio_id.)

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_prompt_context_enrichment.py::test_trade_analyzer_accepts_portfolio_id \
       tests/test_prompt_context_enrichment.py::test_trade_analyzer_no_arg_defaults_to_none \
       tests/test_prompt_context_enrichment.py::test_trade_analyzer_load_transactions_uses_portfolio_id -v
```
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/trade_analyzer.py tests/test_prompt_context_enrichment.py
git commit -m "fix: TradeAnalyzer accepts portfolio_id — was silently reading wrong portfolio transactions"
```

---

## Task 2: Fix EarlyWarningSystem (Bug B) + PortfolioAnalytics benchmark (Bug C)

**Files:**
- Modify: `scripts/early_warning.py:74`
- Modify: `scripts/analytics.py:270-271`
- Test: `tests/test_prompt_context_enrichment.py`

**Background:**
- Bug B: `EarlyWarningSystem.__init__` receives `portfolio_id` but drops it at line 74: `self.trade_analyzer = TradeAnalyzer()`. After Task 1's fix, TradeAnalyzer can accept it — just pass it through.
- Bug C: `PortfolioAnalytics.fetch_benchmark_data()` ignores `self.config` and hardcodes `["^RUT", "IWM"]`. Allcap portfolios using `^GSPC` get wrong benchmark returns in the performance block.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_prompt_context_enrichment.py`:

```python
# ─── Task 2: EarlyWarningSystem Bug B ──────────────────────────────────────────

def test_early_warning_passes_portfolio_id_to_trade_analyzer():
    """EarlyWarningSystem must pass portfolio_id to TradeAnalyzer."""
    from early_warning import EarlyWarningSystem
    with patch("early_warning.load_portfolio_state") as mock_lps, \
         patch("early_warning.TradeAnalyzer") as mock_ta:
        mock_lps.return_value = MagicMock(positions=MagicMock(empty=True),
                                           snapshots=MagicMock(empty=True),
                                           transactions=MagicMock(empty=True))
        EarlyWarningSystem(portfolio_id="my-portfolio")
        mock_ta.assert_called_once_with(portfolio_id="my-portfolio")


# ─── Task 2: PortfolioAnalytics Bug C ──────────────────────────────────────────

def test_portfolio_analytics_benchmark_uses_config():
    """fetch_benchmark_data must use config benchmark_symbol, not hardcoded ^RUT."""
    from analytics import PortfolioAnalytics
    with patch("analytics.load_portfolio_state") as mock_lps:
        mock_state = MagicMock()
        mock_state.config = {
            "benchmark_symbol": "^GSPC",
            "fallback_benchmark": "SPY",
        }
        mock_state.snapshots = MagicMock(empty=True)
        mock_lps.return_value = mock_state

        pa = PortfolioAnalytics(portfolio_id="adjacent-supporters-of-ai")

        import yfinance as yf
        with patch("yfinance.download", return_value=MagicMock(empty=True)) as mock_dl:
            pa.fetch_benchmark_data("2026-01-01", "2026-03-25")
            # First call should use ^GSPC (from config), not ^RUT
            first_ticker = mock_dl.call_args_list[0][0][0]
            assert first_ticker == "^GSPC", f"Expected ^GSPC, got {first_ticker}"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_prompt_context_enrichment.py::test_early_warning_passes_portfolio_id_to_trade_analyzer \
       tests/test_prompt_context_enrichment.py::test_portfolio_analytics_benchmark_uses_config -v
```
Expected: 2 FAIL

- [ ] **Step 3: Fix Bug B in `early_warning.py`**

In `scripts/early_warning.py`, line 74, change:
```python
        self.trade_analyzer = TradeAnalyzer()
```
to:
```python
        self.trade_analyzer = TradeAnalyzer(portfolio_id=portfolio_id)
```

- [ ] **Step 4: Fix Bug C in `analytics.py`**

In `scripts/analytics.py`, replace lines 269-277 (the `fetch_benchmark_data` try block content):

```python
    def fetch_benchmark_data(self, start_date: str, end_date: str) -> pd.Series:
        """Fetch benchmark returns using portfolio's configured benchmark."""
        try:
            import yfinance as yf

            primary = self.config.get("benchmark_symbol", "^RUT")
            fallback = self.config.get("fallback_benchmark", "IWM")
            for ticker in [primary, fallback]:
                try:
                    data = yf.download(ticker, start=start_date, end=end_date, progress=False)
                    if not data.empty and "Close" in data.columns:
                        return data["Close"].pct_change().dropna()
                except Exception as e:
                    print(f"Warning: benchmark download failed for {ticker}: {e}")
                    continue

            return pd.Series()
        except ImportError:
            return pd.Series()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_prompt_context_enrichment.py::test_early_warning_passes_portfolio_id_to_trade_analyzer \
       tests/test_prompt_context_enrichment.py::test_portfolio_analytics_benchmark_uses_config -v
```
Expected: 2 PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/early_warning.py scripts/analytics.py tests/test_prompt_context_enrichment.py
git commit -m "fix: EarlyWarningSystem passes portfolio_id to TradeAnalyzer; PortfolioAnalytics reads benchmark from config"
```

---

## Task 3: Gather prompt_extras and thread through function signatures

**Files:**
- Modify: `scripts/unified_analysis.py` (inside `_run_ai_driven_analysis`, line ~148-163)
- Modify: `scripts/ai_allocator.py:24-34` (`run_ai_allocation` signature) and `131-143` (`_build_allocation_prompt` signature)
- Test: `tests/test_prompt_context_enrichment.py`

**Background:** All five data items are gathered inside `_run_ai_driven_analysis` (in `unified_analysis.py`) right before the `run_ai_allocation` call. They're bundled into a `prompt_extras` dict and passed as a new optional parameter through `run_ai_allocation` → `_build_allocation_prompt`. Each gather is wrapped in try/except so failures are non-fatal.

Note: `from trade_analyzer import TradeAnalyzer` is already imported at the top of `unified_analysis.py` (line 56). Add `from analytics import PortfolioAnalytics` and `from factor_learning import FactorLearner` to the top-level imports. Also add `from early_warning import get_warnings` alongside the existing `from early_warning import get_warning_severity`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_prompt_context_enrichment.py`:

```python
# ─── Task 3: prompt_extras threading ───────────────────────────────────────────

def test_run_ai_allocation_accepts_prompt_extras():
    """run_ai_allocation must accept a prompt_extras optional kwarg."""
    import inspect
    from ai_allocator import run_ai_allocation
    sig = inspect.signature(run_ai_allocation)
    assert "prompt_extras" in sig.parameters
    assert sig.parameters["prompt_extras"].default is None


def test_build_allocation_prompt_accepts_prompt_extras():
    """_build_allocation_prompt must accept a prompt_extras optional kwarg."""
    import inspect
    from ai_allocator import _build_allocation_prompt
    sig = inspect.signature(_build_allocation_prompt)
    assert "prompt_extras" in sig.parameters
    assert sig.parameters["prompt_extras"].default is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_prompt_context_enrichment.py::test_run_ai_allocation_accepts_prompt_extras \
       tests/test_prompt_context_enrichment.py::test_build_allocation_prompt_accepts_prompt_extras -v
```
Expected: 2 FAIL

- [ ] **Step 3: Add imports to `unified_analysis.py`**

Three import changes are needed. Make them precisely:

**Change 1** — line 33: extend the `early_warning` import to add `get_warnings`:
```python
# Before:
from early_warning import get_warning_severity
# After:
from early_warning import get_warning_severity, get_warnings
```

**Change 2** — after the `early_warning` line, add a new import for `PortfolioAnalytics`:
```python
from analytics import PortfolioAnalytics
```

**Change 3** — line 40: extend the existing `factor_learning` import (do NOT add a second `from factor_learning import` line):
```python
# Before:
from factor_learning import apply_weight_adjustments as _apply_weight_adjustments
# After:
from factor_learning import apply_weight_adjustments as _apply_weight_adjustments, FactorLearner
```

- [ ] **Step 4: Add prompt_extras gathering to `_run_ai_driven_analysis`**

In `scripts/unified_analysis.py`, locate the call to `run_ai_allocation` (around line 153). Insert the following block immediately **before** the `# Build sector map from positions + watchlist` comment (around line 148):

```python
    # ─── Gather rich context for AI prompt ─────────────────────────────────────
    prompt_extras: dict = {
        "trade_stats": None,
        "portfolio_metrics": None,
        "warnings": [],
        "days_since_last_buy": None,
        "factor_summary": None,
    }
    _portfolio_id = state.portfolio_id

    try:
        prompt_extras["warnings"] = get_warnings(portfolio_id=_portfolio_id)
    except Exception as e:
        print(f"  [AI-Driven] Warnings fetch failed (non-fatal): {e}")

    try:
        trade_stats = TradeAnalyzer(portfolio_id=_portfolio_id).calculate_trade_stats()
        prompt_extras["trade_stats"] = trade_stats
    except Exception as e:
        print(f"  [AI-Driven] TradeAnalyzer failed (non-fatal): {e}")

    try:
        prompt_extras["portfolio_metrics"] = PortfolioAnalytics(portfolio_id=_portfolio_id).calculate_all_metrics()
    except Exception as e:
        print(f"  [AI-Driven] PortfolioAnalytics failed (non-fatal): {e}")

    try:
        import pandas as _pd
        if not state.transactions.empty:
            buys = state.transactions[state.transactions["action"] == "BUY"]
            if not buys.empty:
                last_buy_date = _pd.to_datetime(buys["date"]).max().date()
                prompt_extras["days_since_last_buy"] = (date.today() - last_buy_date).days
    except Exception as e:
        print(f"  [AI-Driven] Cash idle time failed (non-fatal): {e}")

    try:
        summary = FactorLearner(portfolio_id=_portfolio_id).get_factor_summary()
        if summary.get("status") == "ok":
            prompt_extras["factor_summary"] = summary
    except Exception as e:
        print(f"  [AI-Driven] FactorLearner failed (non-fatal): {e}")
```

- [ ] **Step 5: Pass prompt_extras to run_ai_allocation**

In `scripts/unified_analysis.py`, add `prompt_extras=prompt_extras` to the `run_ai_allocation(...)` call (around line 153):

```python
    reviewed_actions = run_ai_allocation(
        state=state,
        layer1_sells=layer1_sell_actions,
        scored_candidates=scored_candidates,
        sector_map=sector_map,
        regime=regime,
        warning_severity=warning_severity,
        strategy_dna=strategy_dna,
        info_cache=info_cache,
        regime_analysis=state.regime_analysis,
        prompt_extras=prompt_extras,
    )
```

- [ ] **Step 6: Add `prompt_extras` param to `run_ai_allocation` in `ai_allocator.py`**

In `scripts/ai_allocator.py`, update the `run_ai_allocation` signature (lines 24-52) to add `prompt_extras`:

```python
def run_ai_allocation(
    state,
    layer1_sells: list,
    scored_candidates: list,
    sector_map: dict,
    regime: MarketRegime,
    warning_severity: str,
    strategy_dna: str,
    info_cache: Optional[dict] = None,
    regime_analysis: Optional[RegimeAnalysis] = None,
    prompt_extras: Optional[dict] = None,
) -> list:
```

And pass it through to `_build_allocation_prompt` — update the call at line ~80:

```python
    prompt = _build_allocation_prompt(
        state=state,
        layer1_sells=layer1_sells,
        scored_candidates=scored_candidates,
        sector_map=sector_map,
        regime=regime,
        warning_severity=warning_severity,
        strategy_dna=strategy_dna,
        available_cash=available_cash,
        info_cache=info_cache,
        full_watchlist=full_watchlist,
        regime_analysis=regime_analysis,
        prompt_extras=prompt_extras,
    )
```

- [ ] **Step 7: Add `prompt_extras` param to `_build_allocation_prompt` in `ai_allocator.py`**

Update the `_build_allocation_prompt` signature (line ~131):

```python
def _build_allocation_prompt(
    state,
    layer1_sells: list,
    scored_candidates: list,
    sector_map: dict,
    regime: MarketRegime,
    warning_severity: str,
    strategy_dna: str,
    available_cash: float,
    info_cache: Optional[dict] = None,
    full_watchlist: bool = False,
    regime_analysis: Optional[RegimeAnalysis] = None,
    prompt_extras: Optional[dict] = None,
) -> str:
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
pytest tests/test_prompt_context_enrichment.py::test_run_ai_allocation_accepts_prompt_extras \
       tests/test_prompt_context_enrichment.py::test_build_allocation_prompt_accepts_prompt_extras -v
```
Expected: 2 PASS

- [ ] **Step 9: Commit**

```bash
git add scripts/unified_analysis.py scripts/ai_allocator.py tests/test_prompt_context_enrichment.py
git commit -m "feat: gather prompt_extras in _run_ai_driven_analysis and thread through to _build_allocation_prompt"
```

---

## Task 4: Render 5 new context blocks in the prompt

**Files:**
- Modify: `scripts/ai_allocator.py` (inside `_build_allocation_prompt`)
- Test: `tests/test_prompt_context_enrichment.py`

**Background:** Five enrichments to the prompt:
1. **Position age** — add `(Xd held)` to each position line. Source: `entry_date` column in `state.positions`.
2. **Cash idle time** — add `(idle Xd — last buy YYYY-MM-DD)` to the Current Cash line. Source: `prompt_extras["days_since_last_buy"]`.
3. **PORTFOLIO PERFORMANCE block** — shown when `trade_stats.total_trades >= 5` AND `portfolio_metrics` is not None.
4. **ACTIVE ALERTS block** — shown when `warnings` list is non-empty.
5. **FACTOR INTELLIGENCE block** — shown when `factor_summary` is available AND `trade_stats.total_trades >= 10`.

All blocks are computed before the f-string and inserted at the right positions. `prompt_extras=None` means all new sections are silently omitted.

Also add to `ai_allocator.py` imports at the top:
```python
import pandas as pd
from datetime import date, timedelta
```

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_prompt_context_enrichment.py`:

```python
# ─── Task 4: prompt block rendering ────────────────────────────────────────────

import pandas as pd
from datetime import date, timedelta
from unittest.mock import MagicMock


def _make_state(entry_date=None, cash=50000.0, total_equity=100000.0):
    """Build a minimal mock PortfolioState for prompt tests."""
    pos_data = {}
    if entry_date:
        pos_data = {
            "ticker": ["AROC"],
            "shares": [100],
            "current_price": [36.84],
            "unrealized_pnl_pct": [2.8],
            "market_value": [3684.0],
            "stop_loss": [32.96],
            "take_profit": [42.99],
            "entry_date": [entry_date],
        }
    positions = pd.DataFrame(pos_data)
    state = MagicMock()
    state.positions = positions
    state.cash = cash
    state.total_equity = total_equity
    state.num_positions = len(positions)
    state.config = {"full_watchlist_prompt": False}
    state.portfolio_id = "test"
    return state


def _run_prompt(prompt_extras=None, entry_date=None):
    """Helper: run _build_allocation_prompt with minimal args, return prompt string."""
    from ai_allocator import _build_allocation_prompt
    from market_regime import MarketRegime
    state = _make_state(entry_date=entry_date)
    return _build_allocation_prompt(
        state=state,
        layer1_sells=[],
        scored_candidates=[],
        sector_map={},
        regime=MarketRegime.BULL,
        warning_severity="NORMAL",
        strategy_dna="Test strategy",
        available_cash=50000.0,
        prompt_extras=prompt_extras,
    )


def test_prompt_includes_days_held_when_entry_date_set():
    """Position lines must include (Xd held) when entry_date is available."""
    entry = (date.today() - timedelta(days=20)).isoformat()
    prompt = _run_prompt(entry_date=entry)
    assert "20d held" in prompt or "20 days" in prompt.lower() or "(20d" in prompt


def test_prompt_includes_cash_idle_note():
    """Current Cash line must include idle time when days_since_last_buy is set."""
    extras = {"trade_stats": None, "portfolio_metrics": None,
              "warnings": [], "days_since_last_buy": 8, "factor_summary": None}
    prompt = _run_prompt(prompt_extras=extras)
    assert "idle 8" in prompt or "8 days" in prompt.lower()


def test_prompt_includes_fresh_portfolio_note_when_no_buys():
    """Current Cash line must say 'no buys yet' when days_since_last_buy is None."""
    extras = {"trade_stats": None, "portfolio_metrics": None,
              "warnings": [], "days_since_last_buy": None, "factor_summary": None}
    prompt = _run_prompt(prompt_extras=extras)
    assert "no buys yet" in prompt or "fresh portfolio" in prompt


def test_prompt_includes_perf_block_when_enough_trades():
    """PORTFOLIO PERFORMANCE block must appear when >= 5 trades and metrics available."""
    from trade_analyzer import TradeStats
    from analytics import RiskMetrics
    stats = TradeStats(total_trades=10, winning_trades=6, losing_trades=4,
                       win_rate_pct=60.0, avg_win_pct=8.4, avg_loss_pct=-4.1,
                       profit_factor=2.05, avg_trade_pct=2.5,
                       best_trade_ticker="X", best_trade_pct=15.0,
                       worst_trade_ticker="Y", worst_trade_pct=-6.0,
                       total_realized_pnl=3200.0, open_positions=2)
    metrics = RiskMetrics(sharpe_ratio=1.2, sortino_ratio=1.5,
                          max_drawdown_pct=-8.0, max_drawdown_start="", max_drawdown_end="",
                          calmar_ratio=1.0, volatility_annual=15.0,
                          total_return_pct=12.3, cagr_pct=10.0,
                          current_drawdown_pct=-2.1, exposure_pct=75.0, days_tracked=90,
                          benchmark_return_pct=8.1, alpha_pct=4.2)
    extras = {"trade_stats": stats, "portfolio_metrics": metrics,
              "warnings": [], "days_since_last_buy": None, "factor_summary": None}
    prompt = _run_prompt(prompt_extras=extras)
    assert "PORTFOLIO PERFORMANCE" in prompt
    assert "Win rate" in prompt
    assert "60%" in prompt


def test_prompt_omits_perf_block_under_5_trades():
    """PORTFOLIO PERFORMANCE block must be omitted when < 5 completed trades."""
    from trade_analyzer import TradeStats
    from analytics import RiskMetrics
    stats = TradeStats(total_trades=3, winning_trades=2, losing_trades=1,
                       win_rate_pct=66.7, avg_win_pct=5.0, avg_loss_pct=-3.0,
                       profit_factor=3.3, avg_trade_pct=2.3,
                       best_trade_ticker="X", best_trade_pct=8.0,
                       worst_trade_ticker="Y", worst_trade_pct=-3.0,
                       total_realized_pnl=700.0, open_positions=1)
    metrics = RiskMetrics(sharpe_ratio=1.0, sortino_ratio=1.2,
                          max_drawdown_pct=-3.0, max_drawdown_start="", max_drawdown_end="",
                          calmar_ratio=1.0, volatility_annual=10.0,
                          total_return_pct=5.0, cagr_pct=4.0,
                          current_drawdown_pct=-1.0, exposure_pct=60.0, days_tracked=30,
                          benchmark_return_pct=3.0, alpha_pct=2.0)
    extras = {"trade_stats": stats, "portfolio_metrics": metrics,
              "warnings": [], "days_since_last_buy": None, "factor_summary": None}
    prompt = _run_prompt(prompt_extras=extras)
    assert "PORTFOLIO PERFORMANCE" not in prompt


def test_prompt_includes_alerts_block_when_warnings_exist():
    """ACTIVE ALERTS block must appear when warnings list is non-empty."""
    from early_warning import Warning, WarningSeverity
    from datetime import datetime
    w = Warning(id="low_win_rate", title="Low Win Rate",
                description="38% over last 10 trades — below 45% threshold",
                severity=WarningSeverity.HIGH, category="performance")
    extras = {"trade_stats": None, "portfolio_metrics": None,
              "warnings": [w], "days_since_last_buy": None, "factor_summary": None}
    prompt = _run_prompt(prompt_extras=extras)
    assert "ACTIVE ALERTS" in prompt
    assert "Low Win Rate" in prompt
    assert "HIGH" in prompt


def test_prompt_omits_alerts_block_when_no_warnings():
    """ACTIVE ALERTS block must be omitted when warnings list is empty."""
    extras = {"trade_stats": None, "portfolio_metrics": None,
              "warnings": [], "days_since_last_buy": None, "factor_summary": None}
    prompt = _run_prompt(prompt_extras=extras)
    assert "ACTIVE ALERTS" not in prompt


def test_prompt_includes_factor_block_when_enough_trades():
    """FACTOR INTELLIGENCE block must appear when >= 10 trades and factor_summary available."""
    from trade_analyzer import TradeStats
    stats = TradeStats(total_trades=22, winning_trades=14, losing_trades=8,
                       win_rate_pct=63.6, avg_win_pct=8.0, avg_loss_pct=-4.0,
                       profit_factor=2.8, avg_trade_pct=3.5,
                       best_trade_ticker="A", best_trade_pct=20.0,
                       worst_trade_ticker="B", worst_trade_pct=-8.0,
                       total_realized_pnl=9500.0, open_positions=3)
    factor_summary = {
        "status": "ok",
        "total_analyzed_trades": 22,
        "factors": [
            {"factor": "value_timing", "win_rate": 71.0, "total_trades": 22,
             "total_contribution": 4200.0, "trend": "improving", "best_regime": "BULL"},
            {"factor": "price_momentum", "win_rate": 65.0, "total_trades": 22,
             "total_contribution": 3100.0, "trend": "stable", "best_regime": "BULL"},
            {"factor": "quality", "win_rate": 58.0, "total_trades": 22,
             "total_contribution": 2000.0, "trend": "stable", "best_regime": "BULL"},
            {"factor": "volume", "win_rate": 44.0, "total_trades": 22,
             "total_contribution": -400.0, "trend": "declining", "best_regime": "SIDEWAYS"},
        ],
    }
    extras = {"trade_stats": stats, "portfolio_metrics": None,
              "warnings": [], "days_since_last_buy": None, "factor_summary": factor_summary}
    prompt = _run_prompt(prompt_extras=extras)
    assert "FACTOR INTELLIGENCE" in prompt
    assert "value_timing" in prompt
    assert "71%" in prompt or "71.0%" in prompt


def test_prompt_omits_factor_block_under_10_trades():
    """FACTOR INTELLIGENCE block must be omitted when < 10 completed trades."""
    from trade_analyzer import TradeStats
    stats = TradeStats(total_trades=7, winning_trades=4, losing_trades=3,
                       win_rate_pct=57.1, avg_win_pct=6.0, avg_loss_pct=-3.5,
                       profit_factor=2.3, avg_trade_pct=2.2,
                       best_trade_ticker="A", best_trade_pct=10.0,
                       worst_trade_ticker="B", worst_trade_pct=-5.0,
                       total_realized_pnl=2000.0, open_positions=2)
    factor_summary = {
        "status": "ok",
        "factors": [{"factor": "value_timing", "win_rate": 71.0, "total_trades": 7,
                     "total_contribution": 1000.0, "trend": "stable", "best_regime": "BULL"}],
    }
    extras = {"trade_stats": stats, "portfolio_metrics": None,
              "warnings": [], "days_since_last_buy": None, "factor_summary": factor_summary}
    prompt = _run_prompt(prompt_extras=extras)
    assert "FACTOR INTELLIGENCE" not in prompt


def test_prompt_extras_none_produces_no_new_sections():
    """When prompt_extras=None, none of the 5 new blocks appear."""
    prompt = _run_prompt(prompt_extras=None)
    assert "PORTFOLIO PERFORMANCE" not in prompt
    assert "ACTIVE ALERTS" not in prompt
    assert "FACTOR INTELLIGENCE" not in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_prompt_context_enrichment.py -k "test_prompt_includes or test_prompt_omits or test_prompt_extras" -v
```
Expected: All FAIL (no new blocks rendered yet)

- [ ] **Step 3: Add `import pandas as pd` and `from datetime import date, timedelta` to `ai_allocator.py`**

At the top of `scripts/ai_allocator.py`, after the existing imports, add:

```python
import pandas as pd
from datetime import date, timedelta
```

- [ ] **Step 4: Add position age (days held) to positions loop**

In `scripts/ai_allocator.py`, inside the positions loop (around line 149-160), replace the `positions_lines.append(...)` call with:

```python
        # Days held
        days_held = ""
        try:
            entry_date_val = pos.get("entry_date")
            if entry_date_val and str(entry_date_val) not in ("", "nan", "None"):
                days = (date.today() - pd.to_datetime(entry_date_val).date()).days
                days_held = f" ({days}d held)"
        except Exception:
            pass

        positions_lines.append(
            f"  {ticker}: {pos['shares']} shares @ ${pos['current_price']:.2f}, "
            f"P&L {pnl_pct:+.1f}%, weight {weight:.1f}%, sector: {sector}, "
            f"stop ${stop:.2f}, target ${target:.2f}{days_held}"
        )
```

- [ ] **Step 5: Build cash idle note before the f-string**

In `scripts/ai_allocator.py`, add the following block right before the `prompt = f"""...` line (around line 284):

```python
    # Cash idle time note for PORTFOLIO STATE section
    _days_idle = (prompt_extras or {}).get("days_since_last_buy")
    if _days_idle is None:
        _cash_idle_note = " (no buys yet — fresh portfolio)"
    elif _days_idle == 0:
        _cash_idle_note = " (bought today)"
    else:
        _last_buy_str = (date.today() - timedelta(days=_days_idle)).isoformat()
        _cash_idle_note = f" (idle {_days_idle}d — last buy {_last_buy_str})"
```

Note: only show the idle note when `prompt_extras` is not None. If `prompt_extras` is None, use an empty string:

```python
    _cash_idle_note = ""
    if prompt_extras is not None:
        _days_idle = prompt_extras.get("days_since_last_buy")
        if _days_idle is None:
            _cash_idle_note = " (no buys yet — fresh portfolio)"
        elif _days_idle == 0:
            _cash_idle_note = " (bought today)"
        else:
            _last_buy_str = (date.today() - timedelta(days=_days_idle)).isoformat()
            _cash_idle_note = f" (idle {_days_idle}d — last buy {_last_buy_str})"
```

Then in the f-string, change the Current Cash line from:
```
- Current Cash: ${state.cash:,.0f}
```
to:
```
- Current Cash: ${state.cash:,.0f}{_cash_idle_note}
```

- [ ] **Step 6: Build PORTFOLIO PERFORMANCE, ACTIVE ALERTS, FACTOR INTELLIGENCE blocks**

Add the following block immediately after the `_cash_idle_note` computation and before the `prompt = f"""...` line:

```python
    # ─── New context blocks ─────────────────────────────────────────────────────
    _perf_block = ""
    _alerts_block = ""
    _factor_block = ""

    if prompt_extras:
        _stats = prompt_extras.get("trade_stats")
        _metrics = prompt_extras.get("portfolio_metrics")
        _warnings = prompt_extras.get("warnings") or []
        _factor_summary = prompt_extras.get("factor_summary")

        # PORTFOLIO PERFORMANCE — only when >= 5 completed trades AND metrics available
        if _stats and _stats.total_trades >= 5 and _metrics:
            _rr = round(abs(_stats.avg_win_pct / _stats.avg_loss_pct), 2) if _stats.avg_loss_pct else 0.0
            _perf_block = (
                f"PORTFOLIO PERFORMANCE:\n"
                f"  Total return: {_metrics.total_return_pct:+.1f}% vs benchmark {_metrics.benchmark_return_pct:+.1f}%"
                f" (alpha {_metrics.alpha_pct:+.1f}%)\n"
                f"  Current drawdown: {_metrics.current_drawdown_pct:+.1f}% from peak\n"
                f"  Win rate: {_stats.win_rate_pct:.0f}% over {_stats.total_trades} trades"
                f" | avg win {_stats.avg_win_pct:+.1f}% / avg loss {_stats.avg_loss_pct:+.1f}%\n"
                f"  Reward/risk ratio: {_rr:.2f}\n"
            )

        # ACTIVE ALERTS — only when warnings list is non-empty
        if _warnings:
            _high_count = sum(
                1 for w in _warnings if w.severity.value.upper() in ("HIGH", "CRITICAL")
            )
            _hdr = f"ACTIVE ALERTS ({len(_warnings)} total"
            if _high_count:
                _hdr += f", {_high_count} HIGH/CRITICAL"
            _hdr += "):"
            _alert_lines = [
                f"  [{w.severity.value.upper()}] {w.title}: {w.description}"
                for w in _warnings
            ]
            _alerts_block = _hdr + "\n" + "\n".join(_alert_lines) + "\n"

        # FACTOR INTELLIGENCE — only when >= 10 completed trades AND factor_summary available
        if _factor_summary and _stats and _stats.total_trades >= 10:
            _factors = _factor_summary.get("factors", [])
            _top3 = _factors[:3]
            _worst = _factors[-1] if len(_factors) > 3 else None
            _f_lines = ["  Strongest predictors for this portfolio:"]
            for _f in _top3:
                _f_lines.append(
                    f"    {_f['factor']:<20} — {_f['win_rate']:.0f}% win rate, trend: {_f['trend']}"
                )
            if _worst:
                _f_lines.append(
                    f"  Weakest: {_worst['factor']} ({_worst['win_rate']:.0f}% win rate,"
                    f" trend: {_worst['trend']})"
                )
            _f_lines.append(
                "  Note: Weight your decisions toward stocks scoring well on the top factors above."
            )
            _factor_block = (
                f"FACTOR INTELLIGENCE ({_stats.total_trades} completed trades):\n"
                + "\n".join(_f_lines) + "\n"
            )
```

- [ ] **Step 7: Insert new blocks into the f-string**

In the prompt f-string, find the section:
```python
{sector_block}
{regime_block}
```
Replace it with:
```python
{sector_block}
{_perf_block}{_alerts_block}{_factor_block}{regime_block}
```

- [ ] **Step 8: Run all tests**

```bash
pytest tests/test_prompt_context_enrichment.py -v
```
Expected: All tests PASS (13+ tests)

- [ ] **Step 9: Run the full test suite to check for regressions**

```bash
pytest tests/ -v
```
Expected: All existing tests still pass

- [ ] **Step 10: Commit**

```bash
git add scripts/ai_allocator.py tests/test_prompt_context_enrichment.py
git commit -m "feat: render 5 new context blocks in AI allocation prompt (perf, alerts, factor intelligence, position age, cash idle)"
```

---

## Final Verification

- [ ] **Smoke test the analyze pipeline**

```bash
cd /Users/gregmclaughlin/MicroCapRebuilder
source .venv/bin/activate
python3 -c "
from portfolio_state import load_portfolio_state
from unified_analysis import run_unified_analysis
state = load_portfolio_state(fetch_prices=False, portfolio_id='microcap')
print('State loaded OK')
print(f'portfolio_id: {state.portfolio_id}')
print(f'transactions rows: {len(state.transactions)}')
"
```
Expected: prints portfolio_id and transaction count without error.

- [ ] **Push to GitHub**

```bash
git push origin main
```
