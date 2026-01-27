#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate

echo "═══════════════════════════════════════════════════════════"
echo "  MicroCapRebuilder Daily Run - $(date +%Y-%m-%d)"
echo "═══════════════════════════════════════════════════════════"

# 1) Check and execute sells (stop loss / take profit)
echo ""
echo "Step 1: Checking for stop loss / take profit triggers..."
scripts/execute_sells.py

# 2) Pick new stocks from watchlist
echo ""
echo "Step 2: Picking stocks from watchlist..."
scripts/pick_from_watchlist.py

# 3) Update positions with current prices and record daily snapshot
echo ""
echo "Step 3: Updating positions..."
scripts/update_positions.py

# 4) Generate performance chart
echo ""
echo "Step 4: Generating performance chart..."
scripts/generate_graph.py --days 30 --bench ^RUT --fallback IWM

# 5) Overlay stats on chart (uses legacy files for now)
echo ""
echo "Step 5: Overlaying statistics..."
scripts/overlay_stats.py \
  --csv    data/portfolio_update.csv \
  --trades data/trade_log.csv \
  --baseline data/roi_baseline.json \
  --img    charts/performance.png

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Daily run complete!"
echo "═══════════════════════════════════════════════════════════"
