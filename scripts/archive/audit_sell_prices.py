#!/usr/bin/env python3
"""
audit_sell_prices.py

Audits all SELL transactions across active portfolios and corrects prices
that differ from the actual historical close by more than 2%.

Steps:
1. Read each portfolio's transactions.csv
2. For each SELL row, fetch historical close price via yfinance
3. Flag if abs(recorded - actual) / actual > 0.02 (2%)
4. Correct flagged rows in transactions.csv (backs up original first)
5. Update positions.csv if ticker still held
6. Update daily_snapshots.csv for the affected date
7. Print a full summary of every correction
"""

import csv
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yfinance as yf

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ROOT = Path("/Users/gregmclaughlin/MicroCapRebuilder")
DATA = ROOT / "data" / "portfolios"

ACTIVE_PORTFOLIOS = [
    "microcap", "ai", "new", "largeboi",
    "mixed", "klop", "sph", "10k",
    "ai-strategy-sin-stocks", "avg",
]

TOLERANCE = 0.02   # 2%
MAX_RETRIES = 2

# Cache historical close lookups to avoid duplicate fetches
_price_cache: dict[tuple[str, str], float | None] = {}


# ---------------------------------------------------------------------------
# Helper: fetch historical close
# ---------------------------------------------------------------------------
def fetch_historical_close(ticker: str, date_str: str) -> float | None:
    """
    Return the adjusted-close price for `ticker` on `date_str` (YYYY-MM-DD).
    Uses yf.Ticker.history(start=date, end=date+1day).
    Returns None if data unavailable.
    """
    key = (ticker, date_str)
    if key in _price_cache:
        return _price_cache[key]

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        end_dt = dt + timedelta(days=5)   # +5 to handle weekends/holidays
        hist = yf.Ticker(ticker).history(
            start=date_str,
            end=end_dt.strftime("%Y-%m-%d"),
            auto_adjust=True,
        )
        if hist.empty:
            _price_cache[key] = None
            return None
        close = float(hist["Close"].iloc[0])
        _price_cache[key] = close
        return close
    except Exception as e:
        print(f"    [WARN] yfinance error for {ticker} on {date_str}: {e}")
        _price_cache[key] = None
        return None


# ---------------------------------------------------------------------------
# Helper: read CSV preserving raw text (no type coercion)
# ---------------------------------------------------------------------------
def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return (fieldnames, rows_as_dicts)."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    return fieldnames, rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def backup_file(path: Path) -> None:
    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, bak)
    print(f"  [BAK] {bak}")


# ---------------------------------------------------------------------------
# Core audit logic per portfolio
# ---------------------------------------------------------------------------
def audit_portfolio(portfolio_id: str) -> list[dict]:
    """
    Returns list of correction records:
    {portfolio, date, ticker, old_price, new_price, diff_pct, total_old, total_new}
    """
    corrections = []
    port_dir = DATA / portfolio_id
    tx_path = port_dir / "transactions.csv"
    pos_path = port_dir / "positions.csv"
    snap_path = port_dir / "daily_snapshots.csv"

    if not tx_path.exists():
        print(f"  [SKIP] {portfolio_id}: no transactions.csv")
        return corrections

    # --- Read transactions ---
    tx_fields, tx_rows = read_csv(tx_path)

    # --- Find SELL rows ---
    sell_indices = [
        i for i, r in enumerate(tx_rows)
        if r.get("action", "").strip().upper() == "SELL"
    ]

    if not sell_indices:
        print(f"  [OK]   {portfolio_id}: 0 SELL rows")
        return corrections

    print(f"  Checking {len(sell_indices)} SELL row(s) in {portfolio_id}...")

    flagged = []
    for i in sell_indices:
        row = tx_rows[i]
        ticker = row.get("ticker", "").strip()
        date_str = row.get("date", "").strip()
        try:
            recorded_price = float(row.get("price", "0"))
        except ValueError:
            print(f"    [WARN] Bad price in row {i}: {row}")
            continue

        if not ticker or not date_str:
            continue

        actual_close = fetch_historical_close(ticker, date_str)
        if actual_close is None:
            print(f"    [SKIP] {ticker} {date_str}: could not fetch historical close")
            continue

        diff_pct = abs(recorded_price - actual_close) / actual_close
        if diff_pct > TOLERANCE:
            flagged.append({
                "row_idx": i,
                "ticker": ticker,
                "date": date_str,
                "old_price": recorded_price,
                "new_price": actual_close,
                "diff_pct": diff_pct,
                "shares": float(row.get("shares", "0") or 0),
            })
            print(
                f"    [FLAG] {ticker} {date_str}: "
                f"recorded={recorded_price:.4f}  actual={actual_close:.4f}  "
                f"diff={diff_pct*100:.2f}%"
            )
        else:
            print(
                f"    [  ok] {ticker} {date_str}: "
                f"recorded={recorded_price:.4f}  actual={actual_close:.4f}  "
                f"diff={diff_pct*100:.2f}%"
            )

    if not flagged:
        print(f"  [CLEAN] {portfolio_id}: all SELL prices within tolerance")
        return corrections

    # --- Back up transactions.csv before modification ---
    backup_file(tx_path)

    # --- Apply corrections to transactions rows ---
    for item in flagged:
        i = item["row_idx"]
        old_price = item["old_price"]
        new_price = item["new_price"]
        shares = item["shares"]

        old_total = old_price * shares
        new_total = new_price * shares

        # Record correction detail
        corrections.append({
            "portfolio": portfolio_id,
            "date": item["date"],
            "ticker": item["ticker"],
            "old_price": old_price,
            "new_price": new_price,
            "diff_pct": item["diff_pct"],
            "old_total": old_total,
            "new_total": new_total,
        })

        # Update the transactions row
        tx_rows[i]["price"] = f"{new_price:.4f}"
        tx_rows[i]["total_value"] = f"{new_total:.2f}"

    # Write corrected transactions
    write_csv(tx_path, tx_fields, tx_rows)
    print(f"  [SAVE] transactions.csv updated ({len(flagged)} row(s) corrected)")

    # --- Update positions.csv for tickers still held ---
    if pos_path.exists():
        pos_fields, pos_rows = read_csv(pos_path)
        flagged_tickers = {item["ticker"] for item in flagged}
        pos_changed = False

        for pos_row in pos_rows:
            t = pos_row.get("ticker", "").strip()
            if t not in flagged_tickers:
                continue
            # Find the latest actual close for this ticker
            # (use the most recent flagged date for this ticker)
            relevant = sorted(
                [x for x in flagged if x["ticker"] == t],
                key=lambda x: x["date"],
                reverse=True,
            )
            if not relevant:
                continue

            # We only update current_price if the SELL date matches today
            # (sold today — price_high would be stale). For older SELLs the
            # ticker is already gone from positions, but if it is still there
            # we'll refresh with the latest known price.
            latest_item = relevant[0]
            new_price = latest_item["new_price"]

            try:
                shares = float(pos_row.get("shares", "0") or 0)
                avg_cost = float(pos_row.get("avg_cost_basis", "0") or 0)
            except ValueError:
                continue

            market_value = shares * new_price
            unrealized_pnl = (new_price - avg_cost) * shares
            unrealized_pnl_pct = (
                ((new_price - avg_cost) / avg_cost) * 100 if avg_cost else 0
            )

            pos_row["current_price"] = f"{new_price:.4f}"
            pos_row["market_value"] = f"{market_value:.2f}"
            pos_row["unrealized_pnl"] = f"{unrealized_pnl:.2f}"
            pos_row["unrealized_pnl_pct"] = f"{unrealized_pnl_pct:.2f}"
            pos_changed = True
            print(
                f"  [POS]  {t}: current_price updated to {new_price:.4f} "
                f"(was {latest_item['old_price']:.4f})"
            )

        if pos_changed:
            backup_file(pos_path)
            write_csv(pos_path, pos_fields, pos_rows)
            print(f"  [SAVE] positions.csv updated")

    # --- Update daily_snapshots.csv for affected dates ---
    if snap_path.exists():
        snap_fields, snap_rows = read_csv(snap_path)
        affected_dates = {item["date"] for item in flagged}
        snap_changed = False

        # Build a net correction per date: sum of (new_total - old_total)
        correction_by_date: dict[str, float] = {}
        for item in flagged:
            d = item["date"]
            delta = (item["new_price"] - item["old_price"]) * item["shares"]
            correction_by_date[d] = correction_by_date.get(d, 0.0) + delta

        for snap_row in snap_rows:
            snap_date = snap_row.get("date", "").strip()
            if snap_date not in affected_dates:
                continue
            delta = correction_by_date.get(snap_date, 0.0)
            if delta == 0:
                continue
            try:
                old_equity = float(snap_row.get("total_equity", "0") or 0)
                old_cash = float(snap_row.get("cash", "0") or 0)
                old_pnl = float(snap_row.get("day_pnl", "0") or 0)
            except ValueError:
                continue

            # SELL proceeds flow into cash; correcting price changes cash
            new_cash = old_cash + delta
            new_equity = old_equity + delta
            new_pnl = old_pnl + delta

            snap_row["cash"] = f"{new_cash:.2f}"
            snap_row["total_equity"] = f"{new_equity:.2f}"
            snap_row["day_pnl"] = f"{new_pnl:.2f}"
            snap_changed = True
            print(
                f"  [SNAP] {snap_date}: cash {old_cash:.2f}→{new_cash:.2f}, "
                f"equity {old_equity:.2f}→{new_equity:.2f}, "
                f"day_pnl {old_pnl:.2f}→{new_pnl:.2f}  (delta={delta:+.2f})"
            )

        if snap_changed:
            backup_file(snap_path)
            write_csv(snap_path, snap_fields, snap_rows)
            print(f"  [SAVE] daily_snapshots.csv updated")

    return corrections


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("SELL PRICE AUDIT — MicroCapRebuilder")
    print(f"Tolerance: {TOLERANCE*100:.0f}%   Portfolios: {', '.join(ACTIVE_PORTFOLIOS)}")
    print("=" * 70)

    all_corrections = []

    for pid in ACTIVE_PORTFOLIOS:
        print(f"\n{'─'*60}")
        print(f"Portfolio: {pid}")
        corrections = audit_portfolio(pid)
        all_corrections.extend(corrections)

    # --- Final summary ---
    print(f"\n{'='*70}")
    print("SUMMARY OF CORRECTIONS")
    print(f"{'='*70}")

    if not all_corrections:
        print("No corrections needed — all SELL prices are within 2% of historical close.")
        return

    total_delta = 0.0
    for c in all_corrections:
        delta = c["new_total"] - c["old_total"]
        total_delta += delta
        direction = "UP" if c["new_price"] > c["old_price"] else "DOWN"
        print(
            f"  [{c['portfolio']:25s}] {c['ticker']:6s} {c['date']}  "
            f"old={c['old_price']:>10.4f}  new={c['new_price']:>10.4f}  "
            f"diff={c['diff_pct']*100:>6.2f}%  "
            f"total_delta={delta:+.2f}  {direction}"
        )

    print(f"\n  Total corrections : {len(all_corrections)}")
    print(f"  Net value delta   : {total_delta:+.2f}  (across all affected portfolios)")
    print(f"\nDone.")


if __name__ == "__main__":
    main()
