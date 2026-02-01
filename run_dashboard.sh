#!/bin/bash
# Auto-pull latest changes and run the dashboard

cd "$(dirname "$0")"

echo "Pulling latest changes..."
git pull origin claude/add-claude-documentation-SJTa1 --ff-only 2>/dev/null || git pull --ff-only

echo ""
echo "Starting Mommy Bot Dashboard..."
streamlit run scripts/webapp.py
