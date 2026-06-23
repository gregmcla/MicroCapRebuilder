#!/usr/bin/env python3
"""Backfill catalyst-hunting DNA signals (heat_at_entry + market_cap_at_entry_m)
onto historical BUY transactions.

Idempotent: skips rows where the column is already populated. Safe to run
repeatedly — daily after cron, or one-off post-deploy. Reads from
data/social_cache/{pid}_social.json (when present) for heat lookup, and
yfinance for retroactive market cap. yfinance calls are cached by
yf_session so repeated runs are fast.

Usage:
  python3 scripts/backfill_dna_signals.py --portfolio max
  python3 scripts/backfill_dna_signals.py --all-active
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from data_files import get_transactions_file


_DATA_DIR = Path(__file__).parent.parent / "data"


def _load_social_cache(portfolio_id: str) -> dict:
    """Load the social cache; map ticker → latest classification.

    Format on disk (per asym_..._social.json inspection):
      {"AAPL": {"heat": "HOT", "score": 75, "last_updated": "..."}, ...}
    Returns a flat dict {ticker: heat_string}.
    """
    path = _DATA_DIR / "social_cache" / f"{portfolio_id}_social.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
    except Exception:
        return {}
    out: dict[str, str] = {}
    if not isinstance(raw, dict):
        return out
    for ticker, payload in raw.items():
        if isinstance(payload, dict):
            heat = payload.get("heat") or payload.get("classification") or payload.get("status")
            if heat:
                out[str(ticker).upper()] = str(heat).upper()
        elif isinstance(payload, str):
            out[str(ticker).upper()] = payload.upper()
    return out


def _fetch_market_cap_m(ticker: str) -> float:
    """Pull market cap (in $M) via yfinance. Cached by yfinance's own cache —
    repeat calls are instant.

    Returns 0.0 if the lookup fails."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        mcap = info.get("marketCap")
        if mcap is None or mcap <= 0:
            return 0.0
        return round(float(mcap) / 1_000_000.0, 2)
    except Exception:
        return 0.0


def backfill_portfolio(portfolio_id: str, dry_run: bool = False) -> dict:
    """Read transactions.csv, fill heat_at_entry + market_cap_at_entry_m on
    BUY rows where they're empty. Returns counts.
    """
    tx_path = get_transactions_file(portfolio_id)
    if not tx_path.exists():
        return {"portfolio_id": portfolio_id, "skipped": "no transactions file"}

    df = pd.read_csv(tx_path)
    if df.empty:
        return {"portfolio_id": portfolio_id, "skipped": "empty file"}

    # Ensure columns exist (add empty if missing — for files written before #16)
    if "heat_at_entry" not in df.columns:
        df["heat_at_entry"] = ""
    if "market_cap_at_entry_m" not in df.columns:
        df["market_cap_at_entry_m"] = ""

    # Identify BUY rows where either column is empty
    buys_mask = df["action"].astype(str).str.upper() == "BUY"
    needs_heat = buys_mask & (df["heat_at_entry"].astype(str).isin(["", "nan", "None"]))
    needs_mcap = buys_mask & (df["market_cap_at_entry_m"].astype(str).isin(["", "nan", "None"]))
    needs_any = needs_heat | needs_mcap

    n_target = int(needs_any.sum())
    if n_target == 0:
        return {"portfolio_id": portfolio_id, "skipped": "already backfilled",
                "total_buys": int(buys_mask.sum())}

    # Load social cache once
    social = _load_social_cache(portfolio_id)
    print(f"[{portfolio_id}] loaded {len(social)} social cache entries")

    # Iterate only rows that need work — unique tickers (avoid duplicate yfinance fetches)
    tickers_needing_mcap: set[str] = set()
    for idx in df.index[needs_mcap]:
        t = str(df.at[idx, "ticker"]).upper()
        if t:
            tickers_needing_mcap.add(t)

    print(f"[{portfolio_id}] {len(tickers_needing_mcap)} unique tickers need market cap")
    mcap_cache: dict[str, float] = {}
    for i, ticker in enumerate(sorted(tickers_needing_mcap), 1):
        if i % 20 == 0:
            print(f"  ... {i}/{len(tickers_needing_mcap)}")
        mcap_cache[ticker] = _fetch_market_cap_m(ticker)

    # Stamp values
    heat_filled = 0
    mcap_filled = 0
    for idx in df.index[needs_any]:
        ticker = str(df.at[idx, "ticker"]).upper()
        if needs_heat[idx]:
            heat = social.get(ticker, "")
            if heat:
                df.at[idx, "heat_at_entry"] = heat
                heat_filled += 1
        if needs_mcap[idx]:
            mcap = mcap_cache.get(ticker, 0.0)
            if mcap > 0:
                df.at[idx, "market_cap_at_entry_m"] = mcap
                mcap_filled += 1

    if dry_run:
        return {"portfolio_id": portfolio_id, "would_fill_heat": heat_filled,
                "would_fill_mcap": mcap_filled, "dry_run": True}

    # Atomic write
    tmp = tx_path.with_suffix(".csv.tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(tx_path)

    return {
        "portfolio_id": portfolio_id,
        "filled_heat": heat_filled,
        "filled_mcap": mcap_filled,
        "total_buys": int(buys_mask.sum()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio", help="single portfolio id")
    parser.add_argument("--all-active", action="store_true", help="backfill all active portfolios")
    parser.add_argument("--dry-run", action="store_true", help="report counts without writing")
    args = parser.parse_args()

    if not args.portfolio and not args.all_active:
        parser.error("either --portfolio or --all-active is required")

    if args.portfolio:
        result = backfill_portfolio(args.portfolio, dry_run=args.dry_run)
        print(json.dumps(result, indent=2))
        return

    # All active
    registry_path = _DATA_DIR / "portfolios.json"
    if not registry_path.exists():
        print("no portfolios.json — abort")
        return
    data = json.loads(registry_path.read_text())
    results: list[dict] = []
    for pid, meta in (data.get("portfolios") or {}).items():
        if not meta.get("active"):
            continue
        result = backfill_portfolio(pid, dry_run=args.dry_run)
        results.append(result)
        print(json.dumps(result, indent=2))
    print(f"\nbackfilled {len(results)} portfolios")


if __name__ == "__main__":
    main()
