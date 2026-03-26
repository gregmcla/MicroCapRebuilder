#!/usr/bin/env bash
# API health check — restarts uvicorn if the health endpoint stops responding
# Scheduled: every 15 minutes via crontab

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$DIR/cron/logs/api_watchdog.log"
mkdir -p "$(dirname "$LOG")"

HEALTH=$(curl -s --max-time 5 http://localhost:8001/api/health 2>/dev/null || echo "")

if [ "$HEALTH" = '{"status":"ok"}' ]; then
    exit 0
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] API down -- restarting..." >> "$LOG"

cd "$DIR"
source .venv/bin/activate

if [ -f .env ]; then
    set -a; source .env; set +a
fi

pkill -f "uvicorn api.main:app" 2>/dev/null || true
sleep 1

DISABLE_SOCIAL=true nohup uvicorn api.main:app --host 0.0.0.0 --port 8001 \
    >> "$LOG" 2>&1 &

sleep 8
HEALTH=$(curl -s --max-time 5 http://localhost:8001/api/health 2>/dev/null || echo "")
if [ "$HEALTH" = '{"status":"ok"}' ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] API restarted OK" >> "$LOG"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] API restart FAILED" >> "$LOG"
fi
