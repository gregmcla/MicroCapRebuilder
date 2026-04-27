#!/usr/bin/env bash
# API health check + Telegram bot watchdog
# Scheduled: every 15 minutes via crontab

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$DIR/cron/logs/api_watchdog.log"
mkdir -p "$(dirname "$LOG")"

HEALTH=$(curl -s --max-time 5 http://localhost:8001/api/health 2>/dev/null || echo "")

if [[ "$HEALTH" == *'"status":"ok"'* ]]; then
    :
else
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
    if [[ "$HEALTH" == *'"status":"ok"'* ]]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] API restarted OK" >> "$LOG"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] API restart FAILED" >> "$LOG"
    fi
fi

# ── Telegram bot watchdog ─────────────────────────────────────────────────────
BOT_LOG="$DIR/cron/logs/telegram_bot.log"

if ! pgrep -f "telegram_bot.py" > /dev/null 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Telegram bot down -- restarting..." >> "$LOG"

    cd "$DIR"
    source .venv/bin/activate
    if [ -f .env ]; then
        set -a; source .env; set +a
    fi

    nohup python3 scripts/telegram_bot.py >> "$BOT_LOG" 2>&1 &
    sleep 5

    if pgrep -f "telegram_bot.py" > /dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Telegram bot restarted OK" >> "$LOG"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Telegram bot restart FAILED" >> "$LOG"
    fi
fi
