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
