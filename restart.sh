#!/usr/bin/env bash
# Launch GScott — kills any old instances + starts API + Telegram bot + dashboard.
# Usage: ~/MicroCapRebuilder/restart.sh
set -u
cd "$(dirname "$0")"

# Kill anything already running
ps aux | grep -E "uvicorn|telegram_bot|vite" | grep -v grep | awk '{print $2}' | xargs -r kill -9 2>/dev/null
sleep 2

# Start everything
source .venv/bin/activate
DISABLE_SOCIAL=true nohup uvicorn api.main:app --host 0.0.0.0 --port 8001 > /tmp/mcr_api.log 2>&1 &
DISABLE_SOCIAL=true nohup python3 scripts/telegram_bot.py > cron/logs/telegram_bot.log 2>&1 &
(cd dashboard && nohup npm run dev > /tmp/mcr_dashboard.log 2>&1 &)

sleep 5

echo
echo "GScott is running:"
echo "  Dashboard: http://localhost:5173"
echo "  API:       http://localhost:8001"
echo
curl -s -o /dev/null -w "  Dashboard health: %{http_code} (should be 200)\n" http://localhost:5173/
curl -s -o /dev/null -w "  API health:       %{http_code} (should be 200)\n" http://localhost:8001/api/health
