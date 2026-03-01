#!/usr/bin/env python3
"""Run FastAPI server: uvicorn api.main:app --reload --port 8080"""
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

API_PORT = 8080

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=API_PORT, reload=True)
