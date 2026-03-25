#!/bin/bash
# Launch the GScott Trading Cockpit — FastAPI + React dev server
# Usage: ./run_dashboard.sh

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
NC='\033[0m'

cleanup() {
    echo ""
    echo -e "${CYAN}Shutting down...${NC}"
    kill $API_PID $VITE_PID 2>/dev/null
    wait $API_PID $VITE_PID 2>/dev/null
    echo -e "${GREEN}Done.${NC}"
}
trap cleanup EXIT INT TERM

echo -e "${CYAN}Starting GScott Trading Cockpit${NC}"
echo ""

# Start FastAPI
echo -e "  API:       ${GREEN}http://localhost:8001${NC}"
source .venv/bin/activate
uvicorn api.main:app --port 8001 &
API_PID=$!

# Start Vite dev server
echo -e "  Dashboard: ${GREEN}http://localhost:5173${NC}"
cd dashboard
npm run dev -- --host &
VITE_PID=$!
cd "$DIR"

echo ""
echo -e "${CYAN}Keyboard shortcuts: A=analyze  E=execute  R=refresh  1/2/3=tabs${NC}"
echo -e "Press Ctrl+C to stop."
echo ""

# Wait for both processes (macOS bash lacks wait -n)
wait $API_PID $VITE_PID
