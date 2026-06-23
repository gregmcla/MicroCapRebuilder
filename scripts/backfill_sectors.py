#!/usr/bin/env python3
"""Backfill missing sectors on positions.csv across portfolios.

For every position whose `sector` is blank / "nan" / "None" / "Unknown",
look up the sector via yfinance and stamp it in place. ETFs/SPACs that
have no GICS sector get stamped as "ETF" so the field is never empty.

Idempotent: only touches rows that need it. Safe to re-run anytime.

Usage:
  python3 scripts/backfill_sectors.py --portfolio max
  python3 scripts/backfill_sectors.py --all-active
  python3 scripts/backfill_sectors.py --all-active --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import yfinance as yf

from data_files import get_positions_file


_DATA_DIR = Path(__file__).parent.parent / "data"
_BLANK = {"", "nan", "None", "Unknown"}


def _is_blank(s) -> bool:
    """True if sector value is missing/placeholder and needs a backfill."""
    if s is None:
        return True
    txt = str(s).strip()
    return txt in _BLANK


def _resolve_sector(ticker: str) -> str:
    """Look up a sector for one ticker via yfinance. Returns "" on failure
    or "ETF" for ETF/SPAC quoteTypes that lack a GICS sector."""
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception as e:
        print(f"    {ticker}: lookup failed — {e}")
        return ""
    sector = (info.get("sector") or "").strip()
    if sector:
        return sector
    qt = (info.get("quoteType") or "").upper()
    if qt in ("ETF", "MUTUALFUND"):
        return "ETF"
    return ""


def backfill_portfolio(portfolio_id: str, dry_run: bool = False) -> dict:
    pos_path = get_positions_file(portfolio_id)
    if not pos_path.exists():
        return {"portfolio_id": portfolio_id, "skipped": "no positions file"}

    df = pd.read_csv(pos_path)
    if df.empty:
        return {"portfolio_id": portfolio_id, "skipped": "empty positions"}

    if "sector" not in df.columns:
        df["sector"] = ""

    needs_mask = df["sector"].apply(_is_blank)
    n_target = int(needs_mask.sum())
    if n_target == 0:
        return {"portfolio_id": portfolio_id, "skipped": "already complete",
                "total_positions": len(df)}

    print(f"[{portfolio_id}] looking up {n_target} missing sectors…")
    filled = 0
    still_blank: list[str] = []
    for idx in df.index[needs_mask]:
        ticker = str(df.at[idx, "ticker"])
        resolved = _resolve_sector(ticker)
        if resolved:
            df.at[idx, "sector"] = resolved
            filled += 1
            print(f"  ✓ {ticker:10s}  →  {resolved}")
        else:
            still_blank.append(ticker)
            print(f"  ✗ {ticker:10s}  no sector from yfinance")

    if dry_run:
        return {"portfolio_id": portfolio_id, "would_fill": filled,
                "still_blank": still_blank, "dry_run": True}

    # Atomic write
    tmp = pos_path.with_suffix(".csv.tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(pos_path)

    return {
        "portfolio_id": portfolio_id,
        "filled": filled,
        "still_blank": still_blank,
        "total_positions": len(df),
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
