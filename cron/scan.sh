#!/usr/bin/env bash
# Pre-market discovery scan — refreshes all active portfolio watchlists
# Scheduled: 6:30 AM ET, Monday–Friday via crontab
#
# NOTE: Mac sleeps at 11:30 PM daily. cron skips jobs while asleep and does NOT
# catch up. To reliably fire the 6:30 AM scan, add a scheduled wake (one-time
# admin command):
#   sudo pmset repeat wakeorpoweron MTWRF 06:25:00
# Without that, this script will only run when the Mac is already awake.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$DIR/cron/logs"
LOG="$LOG_DIR/scan_$(date +%Y%m%d)_$$.log"
mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

# Belt-and-suspenders: skip weekends
DOW=$(date +%u)
if [ "$DOW" -ge 6 ]; then
    log "Weekend detected -- skipping"
    exit 0
fi

# Overlap guard: prevent a second concurrent scan if the prior one is still running.
# mkdir is atomic on POSIX — if dir already exists, it fails instantly.
LOCKDIR="/tmp/mcr_scan.lock"
if ! mkdir "$LOCKDIR" 2>/dev/null; then
    log "Another scan is already running ($LOCKDIR exists) -- skipping this run"
    exit 0
fi
trap "rmdir '$LOCKDIR' 2>/dev/null || true" EXIT INT TERM

# Keep Mac awake for the duration of this script (no-op if already on AC power).
caffeinate -i &
CAFF_PID=$!
trap "kill $CAFF_PID 2>/dev/null || true; rmdir '$LOCKDIR' 2>/dev/null || true" EXIT INT TERM

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
if [ -z "$PORTFOLIOS" ]; then
    log "ERROR: list_portfolios.py returned no portfolios -- aborting"
    exit 1
fi
COUNT=0
FAILED=0
PORTFOLIOS_OK=""
PORTFOLIOS_FAILED=""

for PORTFOLIO in $PORTFOLIOS; do
    log "Scanning: $PORTFOLIO"
    # 180s per portfolio: warm scans are ~12s, cold (first run) up to ~80s.
    # This prevents a single hung portfolio from wedging the whole job.
    if timeout 180 python3 scripts/watchlist_manager.py --update --portfolio "$PORTFOLIO" >> "$LOG" 2>&1; then
        log "  ok: $PORTFOLIO"
        COUNT=$((COUNT + 1))
        PORTFOLIOS_OK="$PORTFOLIOS_OK $PORTFOLIO"
    else
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            log "  TIMEOUT: $PORTFOLIO (>180s) -- continuing"
        else
            log "  FAILED: $PORTFOLIO (exit $EXIT_CODE) -- continuing"
        fi
        FAILED=$((FAILED + 1))
        PORTFOLIOS_FAILED="$PORTFOLIOS_FAILED $PORTFOLIO"
    fi
done

log "=========================================="
log "SCAN COMPLETE -- $COUNT ok, $FAILED failed"
log "=========================================="

# Send Telegram scan summary (non-fatal)
PORTFOLIOS_OK="${PORTFOLIOS_OK# }"
PORTFOLIOS_FAILED="${PORTFOLIOS_FAILED# }"
python3 scripts/telegram_notifier.py scan-summary \
    --ok "$PORTFOLIOS_OK" \
    --failed "$PORTFOLIOS_FAILED" >> "$LOG" 2>&1 || true
