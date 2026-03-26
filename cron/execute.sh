#!/usr/bin/env bash
# Market-open analyze + execute — AI allocation for all active portfolios
# Scheduled: 9:35 AM ET, Monday–Friday via crontab
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$DIR/cron/logs"
LOG="$LOG_DIR/execute_$(date +%Y%m%d)_$$.log"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# Belt-and-suspenders: skip weekends (cron 1-5 already handles this)
DOW=$(date +%u)
if [ "$DOW" -ge 6 ]; then
    log "Weekend detected -- skipping"
    exit 0
fi

log "=========================================="
log "MARKET-OPEN EXECUTE START"
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
    log "Executing: $PORTFOLIO"
    if python3 scripts/unified_analysis.py --execute --portfolio "$PORTFOLIO" >> "$LOG" 2>&1; then
        log "  ok: $PORTFOLIO"
        COUNT=$((COUNT + 1))
    else
        log "  FAILED: $PORTFOLIO (continuing)"
        FAILED=$((FAILED + 1))
    fi
done

log "=========================================="
log "EXECUTE COMPLETE -- $COUNT ok, $FAILED failed"
log "=========================================="
