#!/usr/bin/env python3
"""
Portfolio State - Single source of truth for all portfolio data.

Consolidates cash calculation (12 places), config loading (30+ places),
regime detection (10+ places), and CSV reads/writes (60+) into one module.

Usage:
    from portfolio_state import load_portfolio_state, save_transaction, save_positions

    state = load_portfolio_state()
    print(f"Cash: ${state.cash:.2f}, Positions: {state.num_positions}")

    state = save_transaction(state, txn_dict)
    save_positions(state)
"""

import json
import time
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from data_files import (
    load_config as _load_config_from_file,
    get_positions_file,
    get_transactions_file,
    get_daily_snapshots_file,
    get_watchlist_file,
    is_paper_mode,
)
from schema import (
    TRANSACTION_COLUMNS,
    POSITION_COLUMNS,
    DAILY_SNAPSHOT_COLUMNS,
    Action,
)
from market_regime import (
    MarketRegime,
    RegimeAnalysis,
    get_regime_analysis as _fetch_regime_analysis,
    get_position_size_multiplier,
)


# ─── Regime Cache ────────────────────────────────────────────────────────────

_regime_cache: Optional[RegimeAnalysis] = None
_regime_cache_time: float = 0
_REGIME_CACHE_TTL = 3600  # 1 hour


def _get_cached_regime_analysis() -> RegimeAnalysis:
    """Get regime analysis with TTL-based caching to avoid duplicate yfinance calls."""
    global _regime_cache, _regime_cache_time

    now = time.time()
    if _regime_cache is not None and (now - _regime_cache_time) < _REGIME_CACHE_TTL:
        return _regime_cache

    _regime_cache = _fetch_regime_analysis()
    _regime_cache_time = now
    return _regime_cache


def invalidate_regime_cache() -> None:
    """Force regime to be re-fetched on next load."""
    global _regime_cache, _regime_cache_time
    _regime_cache = None
    _regime_cache_time = 0


# ─── Portfolio State ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PortfolioState:
    """Immutable snapshot of complete portfolio state."""
    cash: float
    positions: pd.DataFrame
    transactions: pd.DataFrame
    snapshots: pd.DataFrame
    regime: MarketRegime
    regime_analysis: RegimeAnalysis
    positions_value: float
    total_equity: float
    num_positions: int
    config: dict
    timestamp: datetime
    price_cache: dict = field(default_factory=dict)
    price_failures: list = field(default_factory=list)
    stale_alerts: dict = field(default_factory=dict)  # ticker -> consecutive_days (>= 2)
    paper_mode: bool = False

    class Config:
        # Allow pandas DataFrames in frozen dataclass
        arbitrary_types_allowed = True

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other


# ─── Loading ─────────────────────────────────────────────────────────────────

def load_portfolio_state(fetch_prices: bool = True) -> PortfolioState:
    """
    Single entry point to load complete portfolio state.

    Loads config, positions, transactions, snapshots, calculates cash,
    detects regime (cached), and optionally fetches current prices.

    Args:
        fetch_prices: If True, fetch current prices for all positions via yfinance.

    Returns:
        PortfolioState with all data loaded.
    """
    config = _load_config_from_file()
    paper_mode = is_paper_mode()

    # Load CSVs
    positions = _load_csv(get_positions_file(), POSITION_COLUMNS)
    transactions = _load_csv(get_transactions_file(), TRANSACTION_COLUMNS)
    snapshots = _load_csv(get_daily_snapshots_file(), DAILY_SNAPSHOT_COLUMNS)

    # Calculate cash from transactions
    cash = calculate_cash(transactions, config["starting_capital"])

    # Get market regime (cached)
    regime_analysis = _get_cached_regime_analysis()
    regime = regime_analysis.regime

    # Fetch prices and update positions if requested
    price_cache = {}
    price_failures = []

    # Always load stale alerts from tracker (even without fresh price fetch)
    stale_tracker = _load_stale_tracker()
    stale_alerts = {t: days for t, days in stale_tracker.items() if days >= 2}

    if fetch_prices and not positions.empty:
        tickers = positions["ticker"].tolist()
        price_cache, price_failures = fetch_prices_batch(tickers)

        # Update positions with fetched prices
        positions = _update_positions_with_prices(positions, price_cache)

        # Track consecutive price fetch failures
        successful = [t for t in tickers if t not in price_failures]
        stale_alerts = update_stale_tracker(price_failures, successful)

    # Calculate derived values
    positions_value = float(positions["market_value"].sum()) if not positions.empty else 0.0
    total_equity = positions_value + cash
    num_positions = len(positions)

    return PortfolioState(
        cash=cash,
        positions=positions,
        transactions=transactions,
        snapshots=snapshots,
        regime=regime,
        regime_analysis=regime_analysis,
        positions_value=positions_value,
        total_equity=total_equity,
        num_positions=num_positions,
        config=config,
        timestamp=datetime.now(),
        price_cache=price_cache,
        price_failures=price_failures,
        stale_alerts=stale_alerts,
        paper_mode=paper_mode,
    )


def _load_csv(path, columns) -> pd.DataFrame:
    """Load a CSV file, returning empty DataFrame with correct columns if missing."""
    if path.exists():
        df = pd.read_csv(path)
        if not df.empty:
            return df
    return pd.DataFrame(columns=columns)


def _update_positions_with_prices(positions: pd.DataFrame, price_cache: dict) -> pd.DataFrame:
    """Update positions DataFrame with fetched prices and recalculate P&L."""
    df = positions.copy()

    for idx, row in df.iterrows():
        ticker = row["ticker"]
        current_price = price_cache.get(ticker)

        if current_price is None or current_price <= 0:
            # Keep existing price as fallback
            continue

        shares = row["shares"]
        avg_cost = row["avg_cost_basis"]
        market_value = shares * current_price
        cost_value = shares * avg_cost
        unrealized_pnl = market_value - cost_value
        unrealized_pnl_pct = (unrealized_pnl / cost_value * 100) if cost_value > 0 else 0

        df.at[idx, "current_price"] = round(current_price, 2)
        df.at[idx, "market_value"] = round(market_value, 2)
        df.at[idx, "unrealized_pnl"] = round(unrealized_pnl, 2)
        df.at[idx, "unrealized_pnl_pct"] = round(unrealized_pnl_pct, 2)

    return df


# ─── Cash Calculation ────────────────────────────────────────────────────────

def calculate_cash(transactions: pd.DataFrame, starting_capital: float) -> float:
    """
    Calculate available cash from transaction history.

    This is THE single source of truth for cash. All scripts should use this
    (via load_portfolio_state) instead of their own calculation.

    Args:
        transactions: DataFrame with transaction history.
        starting_capital: Starting capital from config.

    Returns:
        Available cash balance.
    """
    if transactions.empty:
        return starting_capital

    total_spent = 0.0
    total_received = 0.0

    for _, row in transactions.iterrows():
        action = row["action"]
        value = float(row["total_value"])

        if action in (Action.BUY, "BUY", Action.ADD, "ADD"):
            total_spent += value
        elif action in (Action.SELL, "SELL", Action.TRIM, "TRIM"):
            total_received += value

    return starting_capital - total_spent + total_received


# ─── yfinance Helpers ───────────────────────────────────────────────────────

def flatten_yf_close(df: pd.DataFrame) -> pd.Series:
    """
    Extract Close prices as a flat Series from a yfinance DataFrame.

    Handles the multi-level column issue where newer yfinance versions
    return MultiIndex columns (e.g., ('Close', 'AAPL')) instead of flat ones.
    """
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close


# ─── Price Fetching ──────────────────────────────────────────────────────────

def fetch_prices_batch(tickers: list) -> tuple[dict, list]:
    """
    Fetch current prices for multiple tickers in a single yfinance call.

    Args:
        tickers: List of ticker symbols.

    Returns:
        Tuple of (price_cache dict, failed_tickers list).
    """
    if not tickers:
        return {}, []

    prices = {}
    failures = []

    # yfinance supports batch downloads
    try:
        df = yf.download(tickers, period="1d", progress=False, auto_adjust=True)
        if not df.empty:
            close_col = df["Close"]
            if isinstance(close_col, pd.Series):
                # Single ticker - close_col is a Series
                if len(tickers) == 1:
                    price = float(close_col.iloc[-1])
                    if pd.notna(price) and price > 0:
                        prices[tickers[0]] = price
                    else:
                        failures.append(tickers[0])
            else:
                # Multiple tickers - close_col is a DataFrame
                for ticker in tickers:
                    if ticker in close_col.columns:
                        val = close_col[ticker].iloc[-1]
                        if pd.notna(val) and float(val) > 0:
                            prices[ticker] = float(val)
                        else:
                            failures.append(ticker)
                    else:
                        failures.append(ticker)
    except Exception as e:
        print(f"  [warn] Batch price fetch failed: {e}")
        # Fall back to individual fetches
        for ticker in tickers:
            try:
                single_df = yf.download(ticker, period="1d", progress=False, auto_adjust=True)
                if not single_df.empty:
                    close_col = flatten_yf_close(single_df)
                    price = float(close_col.iloc[-1])
                    if pd.notna(price) and price > 0:
                        prices[ticker] = price
                    else:
                        failures.append(ticker)
                else:
                    failures.append(ticker)
            except Exception:
                failures.append(ticker)

    return prices, failures


# ─── Stale Price Tracking ───────────────────────────────────────────────────

_STALE_TRACKER_FILE = Path(__file__).parent.parent / "data" / "stale_prices.json"


def _load_stale_tracker() -> dict:
    """Load stale price tracker: {ticker: consecutive_failures}."""
    if _STALE_TRACKER_FILE.exists():
        with open(_STALE_TRACKER_FILE) as f:
            return json.load(f)
    return {}


def _save_stale_tracker(tracker: dict) -> None:
    """Persist stale tracker to disk."""
    with open(_STALE_TRACKER_FILE, "w") as f:
        json.dump(tracker, f, indent=2)


def update_stale_tracker(price_failures: list, successful_tickers: list) -> dict:
    """
    Update stale price tracker after a price fetch.

    Returns dict of {ticker: consecutive_days} for tickers stale >= 2 days.
    """
    tracker = _load_stale_tracker()

    # Reset successful fetches
    for t in successful_tickers:
        tracker.pop(t, None)

    # Increment failures
    for t in price_failures:
        tracker[t] = tracker.get(t, 0) + 1

    _save_stale_tracker(tracker)
    return {t: days for t, days in tracker.items() if days >= 2}


# ─── Benchmark ──────────────────────────────────────────────────────────────

def fetch_benchmark_value(config: dict) -> Optional[float]:
    """Fetch benchmark value for comparison."""
    for symbol in [config.get("benchmark_symbol", "^RUT"), config.get("fallback_benchmark", "IWM")]:
        try:
            df = yf.download(symbol, period="1d", progress=False, auto_adjust=True)
            if not df.empty:
                close_col = flatten_yf_close(df)
                return round(float(close_col.iloc[-1]), 2)
        except Exception:
            continue
    return None


# ─── Transaction Validation ─────────────────────────────────────────────────

class TransactionValidationError(ValueError):
    """Raised when a transaction fails validation."""
    pass


def validate_transaction(txn: dict, state: PortfolioState) -> None:
    """
    Validate a transaction before persisting.

    Raises TransactionValidationError on failure. This is a money decision —
    invalid transactions must halt execution, not silently pass.

    Args:
        txn: Transaction dict to validate.
        state: Current portfolio state for context (cash, positions).
    """
    required = ["ticker", "action", "shares", "price", "total_value"]
    for f in required:
        if f not in txn or txn[f] is None or txn[f] == "":
            raise TransactionValidationError(f"Missing required field: {f}")

    if float(txn["price"]) <= 0:
        raise TransactionValidationError(f"Invalid price for {txn['ticker']}: {txn['price']}")
    if int(txn["shares"]) <= 0:
        raise TransactionValidationError(f"Invalid shares for {txn['ticker']}: {txn['shares']}")

    # For BUYs: verify cash covers cost
    if txn["action"] in ("BUY", Action.BUY, "ADD", Action.ADD):
        cost = float(txn["shares"]) * float(txn["price"])
        if cost > state.cash + 0.01:  # Small float tolerance
            raise TransactionValidationError(
                f"Insufficient cash for {txn['ticker']}: need ${cost:.2f}, have ${state.cash:.2f}"
            )

    # For SELLs: verify position exists
    if txn["action"] in ("SELL", Action.SELL, "TRIM", Action.TRIM):
        if state.positions.empty or txn["ticker"] not in state.positions["ticker"].values:
            raise TransactionValidationError(f"No position to sell: {txn['ticker']}")


# ─── Transaction Operations ──────────────────────────────────────────────────

def save_transaction(state: PortfolioState, transaction: dict) -> PortfolioState:
    """
    Append a single transaction to the ledger and return updated state.

    Persists to disk immediately and recalculates cash.

    Args:
        state: Current portfolio state.
        transaction: Transaction dict matching TRANSACTION_COLUMNS.

    Returns:
        New PortfolioState with updated transactions and cash.
    """
    return save_transactions_batch(state, [transaction])


def save_transactions_batch(state: PortfolioState, transactions: list) -> PortfolioState:
    """
    Append multiple transactions to the ledger and return updated state.

    Persists to disk immediately and recalculates cash.

    Args:
        state: Current portfolio state.
        transactions: List of transaction dicts.

    Returns:
        New PortfolioState with updated transactions and cash.
    """
    if not transactions:
        return state

    # Validate all transactions before persisting any
    for txn in transactions:
        validate_transaction(txn, state)

    df_new = pd.DataFrame(transactions)
    tx_file = get_transactions_file()

    # Combine with existing
    if not state.transactions.empty:
        df_combined = pd.concat([state.transactions, df_new], ignore_index=True)
    else:
        df_combined = df_new

    # Persist to disk
    df_combined.to_csv(tx_file, index=False)

    # Recalculate cash
    new_cash = calculate_cash(df_combined, state.config["starting_capital"])

    # Recalculate derived values
    positions_value = float(state.positions["market_value"].sum()) if not state.positions.empty else 0.0
    new_equity = positions_value + new_cash

    return replace(
        state,
        transactions=df_combined,
        cash=new_cash,
        total_equity=new_equity,
        timestamp=datetime.now(),
    )


# ─── Position Operations ─────────────────────────────────────────────────────

def update_position(
    state: PortfolioState,
    ticker: str,
    shares: int,
    price: float,
    stop_loss: float,
    take_profit: float,
) -> PortfolioState:
    """
    Add a new position or average into an existing one.

    Does NOT persist to disk — call save_positions() when ready.

    Args:
        state: Current portfolio state.
        ticker: Stock symbol.
        shares: Number of shares bought.
        price: Purchase price per share.
        stop_loss: Stop loss price.
        take_profit: Take profit price.

    Returns:
        New PortfolioState with updated positions.
    """
    df = state.positions.copy()

    if ticker in df["ticker"].values:
        # Average into existing position
        idx = df[df["ticker"] == ticker].index[0]
        existing_shares = df.at[idx, "shares"]
        existing_cost = df.at[idx, "avg_cost_basis"]
        new_shares = existing_shares + shares
        new_cost = ((existing_shares * existing_cost) + (shares * price)) / new_shares

        df.at[idx, "shares"] = new_shares
        df.at[idx, "avg_cost_basis"] = round(new_cost, 2)
        df.at[idx, "current_price"] = price
        df.at[idx, "market_value"] = round(new_shares * price, 2)
        df.at[idx, "unrealized_pnl"] = round(new_shares * price - new_shares * new_cost, 2)
        df.at[idx, "unrealized_pnl_pct"] = round(
            (price - new_cost) / new_cost * 100 if new_cost > 0 else 0, 2
        )
        df.at[idx, "stop_loss"] = stop_loss
        df.at[idx, "take_profit"] = take_profit
    else:
        # Add new position
        new_row = {
            "ticker": ticker,
            "shares": shares,
            "avg_cost_basis": price,
            "current_price": price,
            "market_value": round(shares * price, 2),
            "unrealized_pnl": 0.0,
            "unrealized_pnl_pct": 0.0,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "entry_date": date.today().isoformat(),
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    positions_value = float(df["market_value"].sum())
    return replace(
        state,
        positions=df,
        positions_value=positions_value,
        total_equity=positions_value + state.cash,
        num_positions=len(df),
        timestamp=datetime.now(),
    )


def remove_position(state: PortfolioState, ticker: str) -> PortfolioState:
    """
    Remove a position (after a full sell).

    Does NOT persist to disk — call save_positions() when ready.

    Args:
        state: Current portfolio state.
        ticker: Ticker to remove.

    Returns:
        New PortfolioState with position removed.
    """
    df = state.positions.copy()
    df = df[df["ticker"] != ticker]

    positions_value = float(df["market_value"].sum()) if not df.empty else 0.0
    return replace(
        state,
        positions=df,
        positions_value=positions_value,
        total_equity=positions_value + state.cash,
        num_positions=len(df),
        timestamp=datetime.now(),
    )


def save_positions(state: PortfolioState) -> None:
    """Persist current positions to CSV."""
    positions_file = get_positions_file()
    state.positions.to_csv(positions_file, index=False)


# ─── Snapshot Operations ─────────────────────────────────────────────────────

def save_snapshot(state: PortfolioState, benchmark_value: Optional[float] = None) -> tuple:
    """
    Append today's daily snapshot. Fetches benchmark if not provided.

    Args:
        state: Current portfolio state.
        benchmark_value: Optional pre-fetched benchmark value.

    Returns:
        Tuple of (total_equity, day_pnl).
    """
    today = date.today().isoformat()

    # Fetch benchmark if not provided
    if benchmark_value is None:
        benchmark_value = fetch_benchmark_value(state.config)

    # Calculate day's P&L from previous snapshot
    day_pnl = 0.0
    day_pnl_pct = 0.0

    if not state.snapshots.empty:
        prev_equity = state.snapshots.iloc[-1]["total_equity"]
        if prev_equity and prev_equity > 0:
            day_pnl = state.total_equity - prev_equity
            day_pnl_pct = (day_pnl / prev_equity) * 100

    snapshot = {
        "date": today,
        "cash": round(state.cash, 2),
        "positions_value": round(state.positions_value, 2),
        "total_equity": round(state.total_equity, 2),
        "day_pnl": round(day_pnl, 2),
        "day_pnl_pct": round(day_pnl_pct, 2),
        "benchmark_value": benchmark_value if benchmark_value else "",
    }

    # Load existing snapshots, remove today's entry if exists, append new
    snapshots_file = get_daily_snapshots_file()
    if snapshots_file.exists():
        df = pd.read_csv(snapshots_file)
        df = df[df["date"] != today]
    else:
        df = pd.DataFrame(columns=DAILY_SNAPSHOT_COLUMNS)

    df = pd.concat([df, pd.DataFrame([snapshot])], ignore_index=True)
    df.to_csv(snapshots_file, index=False)

    return state.total_equity, day_pnl


# ─── Refresh ─────────────────────────────────────────────────────────────────

def refresh_prices(state: PortfolioState) -> PortfolioState:
    """
    Re-fetch all position prices and return updated state.

    Args:
        state: Current portfolio state.

    Returns:
        New PortfolioState with refreshed prices.
    """
    if state.positions.empty:
        return state

    tickers = state.positions["ticker"].tolist()
    price_cache, price_failures = fetch_prices_batch(tickers)
    positions = _update_positions_with_prices(state.positions, price_cache)
    positions_value = float(positions["market_value"].sum())

    return replace(
        state,
        positions=positions,
        positions_value=positions_value,
        total_equity=positions_value + state.cash,
        price_cache=price_cache,
        price_failures=price_failures,
        timestamp=datetime.now(),
    )


# ─── Watchlist ───────────────────────────────────────────────────────────────

def load_watchlist() -> list:
    """Load tickers from watchlist.jsonl."""
    watchlist_path = get_watchlist_file()
    if not watchlist_path.exists():
        return []

    with open(watchlist_path, "r") as f:
        watchlist = [json.loads(line) for line in f if line.strip()]

    return [item["ticker"] for item in watchlist]


# ─── Main (for testing) ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Loading portfolio state...")
    state = load_portfolio_state(fetch_prices=False)

    print(f"\n  Mode:       {'PAPER' if state.paper_mode else 'LIVE'}")
    print(f"  Cash:       ${state.cash:,.2f}")
    print(f"  Positions:  {state.num_positions}")
    print(f"  Pos Value:  ${state.positions_value:,.2f}")
    print(f"  Equity:     ${state.total_equity:,.2f}")
    print(f"  Regime:     {state.regime.value}")
    print(f"  Timestamp:  {state.timestamp.isoformat()}")

    if not state.positions.empty:
        print(f"\n  Holdings:")
        for _, row in state.positions.iterrows():
            pnl_pct = row.get("unrealized_pnl_pct", 0)
            print(f"    {row['ticker']:6s}  {int(row['shares']):3d} shares  ${row['market_value']:>8.2f}  ({pnl_pct:+.1f}%)")
