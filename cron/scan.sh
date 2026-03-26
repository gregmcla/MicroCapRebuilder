#!/usr/bin/env bash
# Pre-market discovery scan — refreshes all active portfolio watchlists
# Scheduled: 6:30 AM ET, Monday–Friday via crontab
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$DIR/cron/logs"
LOG="$LOG_DIR/scan_$(date +%Y%m%d).log"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=========================================="
log "PRE-MARKET SCAN START"
log "=========================================="

cd "$DIR"
source .venv/bin/activate
export DISABLE_SOCIAL=true

if [ -f .env ]; then
    set -a; source .env; set +a
fi

PORTFOLIOS=$(python3 scripts/list_portfolios.py 2>>"$LOG")
COUNT=0
FAILED=0

for PORTFOLIO in $PORTFOLIOS; do
    log "Scanning: $PORTFOLIO"
    if python3 scripts/watchlist_manager.py --update --portfolio "$PORTFOLIO" >> "$LOG" 2>&1; then
        log "  ok: $PORTFOLIO"
        COUNT=$((COUNT + 1))
    else
        log "  FAILED: $PORTFOLIO (continuing)"
        FAILED=$((FAILED + 1))
    fi
done

log "=========================================="
log "SCAN COMPLETE -- $COUNT ok, $FAILED failed"
log "=========================================="
