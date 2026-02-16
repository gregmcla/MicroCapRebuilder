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

# Check for unified mode flag
UNIFIED_MODE=${UNIFIED_MODE:-true}

# Get all active portfolios
PORTFOLIOS=$(python3 scripts/list_portfolios.py)

for PORTFOLIO in $PORTFOLIOS; do
    echo ""
    echo "═══ Processing portfolio: $PORTFOLIO ═══"

    # 0) Run stock discovery (finds new candidates)
    echo ""
    echo "Step 0: Running stock discovery..."
    python3 scripts/watchlist_manager.py --update --portfolio "$PORTFOLIO" 2>/dev/null || echo "  (Discovery skipped - will retry next run)"

    if [ "$UNIFIED_MODE" = "true" ] && [ -n "$ANTHROPIC_API_KEY" -o -n "$OPENAI_API_KEY" ]; then
        # UNIFIED MODE: Single analysis with AI review
        echo ""
        echo "Step 1-3: Running UNIFIED ANALYSIS (Quant + AI Review)..."
        python3 scripts/unified_analysis.py --execute --portfolio "$PORTFOLIO"
    else
        # LEGACY MODE: Separate steps without AI review
        echo ""
        echo "(Running in LEGACY mode - no AI review)"

        echo ""
        echo "Step 1: Checking for stop loss / take profit triggers..."
        python3 scripts/execute_sells.py --portfolio "$PORTFOLIO"

        echo ""
        echo "Step 1b: Checking for patterns..."
        python3 scripts/pattern_detector.py 2>/dev/null || echo "  (Pattern detection skipped)"

        echo ""
        echo "Step 2: Picking stocks from watchlist..."
        python3 scripts/pick_from_watchlist.py --portfolio "$PORTFOLIO"
    fi

    # 3) Update positions with current prices and record daily snapshot
    echo ""
    echo "Step 3: Updating positions..."
    python3 scripts/update_positions.py --portfolio "$PORTFOLIO"

    # 3b) Update factor learning (track which factors are performing)
    echo ""
    echo "Step 3b: Updating factor performance..."
    python3 scripts/factor_learning.py --portfolio "$PORTFOLIO" 2>/dev/null || echo "  (Factor learning skipped - need more trades)"
done

# 4) Generate performance chart (aggregate)
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
