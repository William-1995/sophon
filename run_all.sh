#!/bin/bash
# Run API and frontend. API in background, frontend in foreground.
cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null || source venv/bin/activate 2>/dev/null || true
python start.py &
sleep 3
cd frontend && (test -d node_modules || npm install) && npm run dev
