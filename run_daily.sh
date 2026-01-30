#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate

# Load environment variables from .env if present
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "═══════════════════════════════════════════════════════════"
echo "  MOMMY BOT Daily Run - $(date +%Y-%m-%d)"
echo "═══════════════════════════════════════════════════════════"

# 0) Run stock discovery (finds new candidates)
echo ""
echo "Step 0: Running stock discovery..."
python scripts/watchlist_manager.py --update 2>/dev/null || echo "  (Discovery skipped - will retry next run)"

# 1) Check and execute sells (stop loss / take profit)
echo ""
echo "Step 1: Checking for stop loss / take profit triggers..."
scripts/execute_sells.py

# 1b) Detect patterns (alert before picking if something is wrong)
echo ""
echo "Step 1b: Checking for patterns..."
python scripts/pattern_detector.py 2>/dev/null || echo "  (Pattern detection skipped)"

# 2) Pick new stocks from watchlist
echo ""
echo "Step 2: Picking stocks from watchlist..."
scripts/pick_from_watchlist.py

# 3) Update positions with current prices and record daily snapshot
echo ""
echo "Step 3: Updating positions..."
scripts/update_positions.py

# 3b) Update factor learning (track which factors are performing)
echo ""
echo "Step 3b: Updating factor performance..."
python scripts/factor_learning.py 2>/dev/null || echo "  (Factor learning skipped - need more trades)"

# 3c) Run Portfolio Intelligence (AI-driven analysis and actions)
echo ""
echo "Step 3c: Running Portfolio Intelligence..."
if [ -n "$ANTHROPIC_API_KEY" ]; then
    python scripts/execute_intelligence.py 2>/dev/null || echo "  (Intelligence skipped - check API key)"
else
    echo "  (Intelligence skipped - ANTHROPIC_API_KEY not set)"
fi

# 4) Generate performance chart
echo ""
echo "Step 4: Generating performance chart..."
scripts/generate_graph.py --days 30 --bench ^RUT --fallback IWM

# 5) Generate daily report
echo ""
echo "Step 5: Generating daily report..."
scripts/generate_report.py

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Daily run complete!"
echo "═══════════════════════════════════════════════════════════"
