#!/usr/bin/env bash
# Position update + factor learning — runs at noon and post-close
# Scheduled: 12:00 PM ET and 4:15 PM ET, Monday–Friday via crontab
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$DIR/cron/logs"
LOG="$LOG_DIR/update_$(date +%Y%m%d).log"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=========================================="
log "POSITION UPDATE START"
log "=========================================="

cd "$DIR"
source .venv/bin/activate
export DISABLE_SOCIAL=true

if [ -f .env ]; then
    set -a; source .env; set +a
fi

PORTFOLIOS=$(python3 scripts/list_portfolios.py 2>>"$LOG")

for PORTFOLIO in $PORTFOLIOS; do
    log "Updating: $PORTFOLIO"
    python3 scripts/update_positions.py --portfolio "$PORTFOLIO" >> "$LOG" 2>&1 \
        || log "  FAILED: update_positions for $PORTFOLIO"
    # factor_learning is non-fatal (needs >= 5 completed trades)
    python3 scripts/factor_learning.py --portfolio "$PORTFOLIO" >> "$LOG" 2>&1 \
        || true
done

log "=========================================="
log "UPDATE COMPLETE"
log "=========================================="
