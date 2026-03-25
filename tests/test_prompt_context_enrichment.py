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
