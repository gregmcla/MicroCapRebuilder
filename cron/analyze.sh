#!/usr/bin/env bash
# Market-open analyze — AI allocation dry run, sends Telegram proposals for approval
# Scheduled: 9:35 AM ET, Monday–Friday via crontab
# Execution is triggered by user tapping APPROVE in Telegram, not this script.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$DIR/cron/logs"
LOG="$LOG_DIR/analyze_$(date +%Y%m%d)_$$.log"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# Belt-and-suspenders: skip weekends
DOW=$(date +%u)
if [ "$DOW" -ge 6 ]; then
    log "Weekend detected -- skipping"
    exit 0
fi

log "=========================================="
log "MARKET-OPEN ANALYZE START"
log "=========================================="

cd "$DIR"
source .venv/bin/activate
export DISABLE_SOCIAL=true

if [ -f .env ]; then
    set -a; source .env; set +a
fi

PORTFOLIOS=$(python3 scripts/list_portfolios.py 2>>"$LOG")
if [ -z "$PORTFOLIOS" ]; then
    log "ERROR: list_portfolios.py returned no portfolios -- aborting"
    exit 1
fi

COUNT=0
FAILED=0

for PORTFOLIO in $PORTFOLIOS; do
    log "Analyzing: $PORTFOLIO"

    # Call the analyze API endpoint — writes .last_analysis.json, returns HTTP 200 on success
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "http://localhost:8001/api/$PORTFOLIO/analyze" \
        --max-time 300 2>>"$LOG")

    if [ "$HTTP_STATUS" -eq 200 ] 2>/dev/null; then
        log "  analysis ok: $PORTFOLIO (HTTP $HTTP_STATUS)"
        COUNT=$((COUNT + 1))
        # Send Telegram proposal message (non-fatal — if no proposals, sends nothing)
        python3 scripts/telegram_notifier.py proposals \
            --portfolio "$PORTFOLIO" >> "$LOG" 2>&1 || true
    else
        log "  FAILED: $PORTFOLIO (HTTP $HTTP_STATUS)"
        FAILED=$((FAILED + 1))
    fi
done

log "=========================================="
log "ANALYZE COMPLETE -- $COUNT ok, $FAILED failed"
log "=========================================="
