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


# ─── Task 3: prompt_extras threading ───────────────────────────────────────────

def test_run_ai_allocation_accepts_prompt_extras():
    """run_ai_allocation must accept a prompt_extras optional kwarg."""
    from ai_allocator import run_ai_allocation
    sig = inspect.signature(run_ai_allocation)
    assert "prompt_extras" in sig.parameters
    assert sig.parameters["prompt_extras"].default is None


def test_build_allocation_prompt_accepts_prompt_extras():
    """_build_allocation_prompt must accept a prompt_extras optional kwarg."""
    from ai_allocator import _build_allocation_prompt
    sig = inspect.signature(_build_allocation_prompt)
    assert "prompt_extras" in sig.parameters
    assert sig.parameters["prompt_extras"].default is None


# ─── Task 4: prompt block rendering ────────────────────────────────────────────

import pandas as pd
from datetime import date, timedelta


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
    assert "71%" in prompt


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
