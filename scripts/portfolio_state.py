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
# Keyed by benchmark symbol so different portfolios get the right regime.

_regime_cache: dict = {}  # benchmark_symbol -> (RegimeAnalysis, fetch_time)
_REGIME_CACHE_TTL = 3600  # 1 hour

# ─── Live Price Cache ─────────────────────────────────────────────────────────
# Short TTL cache for position prices so repeated state loads don't hammer the
# Public.com API. Keyed by portfolio_id.

_price_cache: dict = {}  # portfolio_id -> (fetch_time, prices, failures, prev_closes)
_PRICE_CACHE_TTL = 60    # seconds


def _fetch_current_prices(
    tickers: list,
    portfolio_id: str,
    bypass_cache: bool = False,
) -> tuple[dict, list, dict]:
    """
    Fetch current prices for a list of position tickers.

    Tries Public.com API first (real-time), falls back to yfinance.
    Results are cached per portfolio for _PRICE_CACHE_TTL seconds to avoid
    hammering the API on repeated state loads.

    Returns:
        (price_cache, failures, prev_close_cache)
    """
    global _price_cache

    if not tickers:
        return {}, [], {}

    now = time.time()
    cached = _price_cache.get(portfolio_id)
    if not bypass_cache and cached:
        fetch_time, prices, failures, prev_closes = cached
        if now - fetch_time < _PRICE_CACHE_TTL:
            return prices, failures, prev_closes

    try:
        from public_quotes import fetch_live_quotes, is_configured as public_configured
        use_public = public_configured()
    except ImportError:
        use_public = False

    if use_public:
        pub_prices, pub_failures = fetch_live_quotes(tickers)
        # Always fetch yfinance for prev_closes (needed for day_change) and
        # cross-validate public.com prices — divergence >15% means bad data.
        yf_tickers = list(set(tickers) | set(pub_failures))
        yf_prices, yf_failures, prev_closes = fetch_prices_batch(yf_tickers)
        validated: dict = {}
        for ticker in tickers:
            pub = pub_prices.get(ticker)
            yf = yf_prices.get(ticker)
            if pub is not None and yf is not None and yf > 0:
                ratio = pub / yf
                if 0.85 <= ratio <= 1.15:
                    validated[ticker] = pub
                else:
                    print(f"  [price] {ticker}: public.com ${pub:.2f} vs yfinance ${yf:.2f} ({ratio:.2f}x) — using yfinance")
                    validated[ticker] = yf
            elif pub is not None:
                validated[ticker] = pub
            elif yf is not None:
                validated[ticker] = yf
        prices = validated
        failures = yf_failures
    else:
        prices, failures, prev_closes = fetch_prices_batch(tickers)

    _price_cache[portfolio_id] = (now, prices, failures, prev_closes)
    return prices, failures, prev_closes


def _get_cached_regime_analysis(config: dict = None) -> RegimeAnalysis:
    """Get regime analysis with TTL-based per-benchmark caching."""
    cfg = config or {}
    benchmark = cfg.get("benchmark_symbol", "^RUT")
    fallback = cfg.get("fallback_benchmark", "IWM")

    now = time.time()
    cached = _regime_cache.get(benchmark)
    if cached is not None and (now - cached[1]) < _REGIME_CACHE_TTL:
        return cached[0]

    analysis = _fetch_regime_analysis(benchmark_symbol=benchmark,
                                      fallback_benchmark=fallback)
    _regime_cache[benchmark] = (analysis, now)
    return analysis


def invalidate_regime_cache() -> None:
    """Force regime to be re-fetched on next load (all benchmarks)."""
    _regime_cache.clear()


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
    portfolio_id: str = ""

    class Config:
        # Allow pandas DataFrames in frozen dataclass
        arbitrary_types_allowed = True

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        return self is other


# ─── Loading ─────────────────────────────────────────────────────────────────

def load_portfolio_state(fetch_prices: bool = True, portfolio_id: str | None = None) -> PortfolioState:
    """
    Single entry point to load complete portfolio state.

    Loads config, positions, transactions, snapshots, calculates cash,
    detects regime (cached), and optionally fetches current prices.

    Args:
        fetch_prices: If True, fetch current prices for all positions via yfinance.
        portfolio_id: Portfolio to load. If None, resolves from registry default.

    Returns:
        PortfolioState with all data loaded.
    """
    if portfolio_id is None:
        from portfolio_registry import get_default_portfolio_id
        portfolio_id = get_default_portfolio_id() or ""

    config = _load_config_from_file(portfolio_id)
    paper_mode = is_paper_mode(portfolio_id)

    # Load CSVs
    positions = _load_csv(get_positions_file(portfolio_id), POSITION_COLUMNS)
    transactions = _load_csv(get_transactions_file(portfolio_id), TRANSACTION_COLUMNS)
    snapshots = _load_csv(get_daily_snapshots_file(portfolio_id), DAILY_SNAPSHOT_COLUMNS)

    # Calculate cash from transactions
    cash = calculate_cash(transactions, config["starting_capital"])

    # Get market regime (cached, using portfolio-specific benchmark)
    regime_analysis = _get_cached_regime_analysis(config)
    regime = regime_analysis.regime

    # Fetch prices and update positions if requested
    price_cache = {}
    price_failures = []

    # Always load stale alerts from tracker (even without fresh price fetch)
    stale_tracker = _load_stale_tracker(portfolio_id)
    stale_alerts = {t: days for t, days in stale_tracker.items() if days >= 2}

    if fetch_prices and not positions.empty:
        tickers = positions["ticker"].tolist()
        price_cache, price_failures, prev_close_cache = _fetch_current_prices(tickers, portfolio_id)

        # Update positions with fetched prices and day change
        positions = _update_positions_with_prices(positions, price_cache, prev_close_cache)

        # Track consecutive price fetch failures
        successful = [t for t in tickers if t not in price_failures]
        stale_alerts = update_stale_tracker(price_failures, successful, portfolio_id)

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
        portfolio_id=portfolio_id,
    )


def _load_csv(path, columns) -> pd.DataFrame:
    """Load a CSV file, returning empty DataFrame with correct columns if missing."""
    if path.exists():
        df = pd.read_csv(path)
        if not df.empty:
            return df
    return pd.DataFrame(columns=columns)


def _update_positions_with_prices(positions: pd.DataFrame, price_cache: dict, prev_close_cache: dict = None) -> pd.DataFrame:
    """Update positions DataFrame with fetched prices and recalculate P&L."""
    df = positions.copy()
    if prev_close_cache is None:
        prev_close_cache = {}

    # Ensure day_change columns exist
    if "day_change" not in df.columns:
        df["day_change"] = 0.0
    if "day_change_pct" not in df.columns:
        df["day_change_pct"] = 0.0
    # Ensure price_high column exists — tracks highest price since entry for trailing stops
    if "price_high" not in df.columns:
        df["price_high"] = df["current_price"]

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

        # Update high watermark — never decreases
        existing_high = float(row.get("price_high", 0) or 0)
        df.at[idx, "price_high"] = round(max(current_price, existing_high), 2)

        # Day change: for positions entered today, use avg_cost as baseline
        # (we didn't own it at yesterday's close, so prev_close is misleading)
        entry_date = str(row.get("entry_date", ""))
        bought_today = entry_date == date.today().isoformat()
        if bought_today:
            day_change = (current_price - avg_cost) * shares
            day_change_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0
            df.at[idx, "day_change"] = round(day_change, 2)
            df.at[idx, "day_change_pct"] = round(day_change_pct, 2)
        else:
            prev_close = prev_close_cache.get(ticker)
            if prev_close and prev_close > 0:
                day_change = (current_price - prev_close) * shares
                day_change_pct = ((current_price - prev_close) / prev_close) * 100
                df.at[idx, "day_change"] = round(day_change, 2)
                df.at[idx, "day_change_pct"] = round(day_change_pct, 2)

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

def fetch_prices_batch(tickers: list) -> tuple[dict, list, dict]:
    """
    Fetch current and previous close prices for multiple tickers in a single yfinance call.

    Args:
        tickers: List of ticker symbols.

    Returns:
        Tuple of (price_cache dict, failed_tickers list, prev_close_cache dict).
    """
    if not tickers:
        return {}, [], {}

    prices = {}
    prev_closes = {}
    failures = []

    def _extract_prices(close_col, ticker, is_series=False):
        """Extract current price and previous close from close column."""
        if is_series:
            vals = close_col.dropna()
        else:
            if ticker not in close_col.columns:
                return None, None
            vals = close_col[ticker].dropna()
        if len(vals) == 0:
            return None, None
        current = float(vals.iloc[-1])
        prev = float(vals.iloc[-2]) if len(vals) >= 2 else None
        return current, prev

    # Use 5d to ensure we get at least 2 trading days for prev close
    try:
        df = yf.download(tickers, period="5d", progress=False, auto_adjust=True)
        if not df.empty:
            # Only compute day_change if the market traded today.
            # yfinance returns daily bars; the last bar's date tells us the last
            # trading day. If it's not today, markets are closed and "current
            # price" == yesterday's close — day_change would be yesterday's
            # gain, not today's (which is 0). So we suppress prev_closes.
            last_trade_date = df.index[-1].date()
            market_open_today = (last_trade_date == date.today())
            close_col = df["Close"]
            if isinstance(close_col, pd.Series):
                # Single ticker - close_col is a Series
                if len(tickers) == 1:
                    current, prev = _extract_prices(close_col, tickers[0], is_series=True)
                    if current and current > 0:
                        prices[tickers[0]] = current
                        if market_open_today and prev and prev > 0:
                            prev_closes[tickers[0]] = prev
                    else:
                        failures.append(tickers[0])
            else:
                # Multiple tickers - close_col is a DataFrame
                for ticker in tickers:
                    current, prev = _extract_prices(close_col, ticker)
                    if current and current > 0:
                        prices[ticker] = current
                        if market_open_today and prev and prev > 0:
                            prev_closes[ticker] = prev
                    else:
                        failures.append(ticker)
    except Exception as e:
        print(f"  [warn] Batch price fetch failed: {e}")
        # Fall back to individual fetches
        for ticker in tickers:
            try:
                single_df = yf.download(ticker, period="5d", progress=False, auto_adjust=True)
                if not single_df.empty:
                    close_col = flatten_yf_close(single_df)
                    current, prev = _extract_prices(close_col, ticker, is_series=True)
                    if current and current > 0:
                        prices[ticker] = current
                        if prev and prev > 0:
                            prev_closes[ticker] = prev
                    else:
                        failures.append(ticker)
                else:
                    failures.append(ticker)
            except Exception as e:
                print(f"Warning: price fetch failed for {ticker}: {e}")
                failures.append(ticker)

    return prices, failures, prev_closes


# ─── Stale Price Tracking ───────────────────────────────────────────────────

_STALE_TRACKER_FILE = Path(__file__).parent.parent / "data" / "stale_prices.json"


def _get_stale_tracker_file(portfolio_id: str = "") -> Path:
    """Get the stale tracker file path, portfolio-aware."""
    if portfolio_id:
        from portfolio_registry import get_portfolio_dir
        return get_portfolio_dir(portfolio_id) / "stale_prices.json"
    return _STALE_TRACKER_FILE


def _load_stale_tracker(portfolio_id: str = "") -> dict:
    """Load stale price tracker: {ticker: consecutive_failures}."""
    tracker_file = _get_stale_tracker_file(portfolio_id)
    if tracker_file.exists():
        with open(tracker_file) as f:
            return json.load(f)
    return {}


def _save_stale_tracker(tracker: dict, portfolio_id: str = "") -> None:
    """Persist stale tracker to disk."""
    tracker_file = _get_stale_tracker_file(portfolio_id)
    with open(tracker_file, "w") as f:
        json.dump(tracker, f, indent=2)


def update_stale_tracker(price_failures: list, successful_tickers: list, portfolio_id: str = "") -> dict:
    """
    Update stale price tracker after a price fetch.

    Returns dict of {ticker: consecutive_days} for tickers stale >= 2 days.
    """
    tracker = _load_stale_tracker(portfolio_id)

    # Reset successful fetches
    for t in successful_tickers:
        tracker.pop(t, None)

    # Increment failures
    for t in price_failures:
        tracker[t] = tracker.get(t, 0) + 1

    _save_stale_tracker(tracker, portfolio_id)
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
        except Exception as e:
            print(f"Warning: benchmark fetch failed for {symbol}: {e}")
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
    tx_file = get_transactions_file(state.portfolio_id)

    # Combine with existing
    if not state.transactions.empty:
        df_combined = pd.concat([state.transactions, df_new], ignore_index=True)
    else:
        df_combined = df_new

    # Persist to disk (atomic write — prevents corruption on crash)
    tmp_file = tx_file.with_name(tx_file.name + ".tmp")
    try:
        df_combined.to_csv(tmp_file, index=False)
        tmp_file.replace(tx_file)
    except Exception:
        tmp_file.unlink(missing_ok=True)
        raise

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
    sector: str = "",
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
        # Update sector if we now have one and didn't before
        if sector and ("sector" not in df.columns or not df.at[idx, "sector"]):
            if "sector" not in df.columns:
                df["sector"] = ""
            df.at[idx, "sector"] = sector
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
            "sector": sector,
            "price_high": price,  # high watermark for trailing stop — updated on every price refresh
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
    positions_file = get_positions_file(state.portfolio_id)
    tmp_file = positions_file.with_name(positions_file.name + ".tmp")
    try:
        state.positions.to_csv(tmp_file, index=False)
        tmp_file.replace(positions_file)
    except Exception:
        tmp_file.unlink(missing_ok=True)
        raise


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

    # Calculate day's P&L from previous day's snapshot (skip today's row)
    day_pnl = 0.0
    day_pnl_pct = 0.0

    if not state.snapshots.empty:
        prior = state.snapshots[state.snapshots["date"] != today]
        if not prior.empty:
            prev_equity = prior.iloc[-1]["total_equity"]
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
    snapshots_file = get_daily_snapshots_file(state.portfolio_id)
    if snapshots_file.exists():
        df = pd.read_csv(snapshots_file)
        df = df[df["date"] != today]
    else:
        df = pd.DataFrame(columns=DAILY_SNAPSHOT_COLUMNS)

    df = pd.concat([df, pd.DataFrame([snapshot])], ignore_index=True)
    tmp_file = snapshots_file.with_name(snapshots_file.name + ".tmp")
    try:
        df.to_csv(tmp_file, index=False)
        tmp_file.replace(snapshots_file)
    except Exception:
        tmp_file.unlink(missing_ok=True)
        raise

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
    price_cache, price_failures, prev_close_cache = _fetch_current_prices(
        tickers, state.portfolio_id, bypass_cache=True
    )
    positions = _update_positions_with_prices(state.positions, price_cache, prev_close_cache)
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

def load_watchlist(portfolio_id: str = "") -> list:
    """Load tickers from watchlist.jsonl."""
    watchlist_path = get_watchlist_file(portfolio_id)
    if not watchlist_path.exists():
        return []

    watchlist = []
    with open(watchlist_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                watchlist.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return [item["ticker"] for item in watchlist]


# ─── Main (for testing) ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    pid = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"Loading portfolio state (portfolio_id={pid!r})...")
    state = load_portfolio_state(fetch_prices=False, portfolio_id=pid)

    print(f"\n  Portfolio:  {state.portfolio_id or '(default)'}")
    print(f"  Mode:       {'PAPER' if state.paper_mode else 'LIVE'}")
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
