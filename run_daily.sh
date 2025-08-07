#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate

# 1) pick & log
scripts/pick_from_watchlist.py

# 2) fix today’s TOTAL
scripts/fix_total_today.py

# 3) regenerate chart
scripts/generate_graph.py --days 30 --bench ^RUT --fallback IWM

# 4) overlay stats
scripts/overlay_stats.py \
  --csv    data/portfolio_update.csv \
  --trades data/trade_log.csv \
  --baseline data/roi_baseline.json \
  --img    charts/performance.png
