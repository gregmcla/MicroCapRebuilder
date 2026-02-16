#!/usr/bin/env python3
"""List active portfolio IDs, one per line. Used by run_daily.sh."""

from portfolio_registry import list_portfolios

for p in list_portfolios(active_only=True):
    print(p.id)
