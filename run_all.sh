#!/bin/bash
# Run API and frontend. Use two terminals or run API in background.
cd "$(dirname "$0")"
echo "1. Start API:  source ../venv/bin/activate && python run_api.py"
echo "2. Start frontend:  cd frontend && npm run dev"
echo ""
echo "Or run API in background:"
source ../venv/bin/activate 2>/dev/null || true
python run_api.py &
sleep 2
cd frontend && npm run dev
