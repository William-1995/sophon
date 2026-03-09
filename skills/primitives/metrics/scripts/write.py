#!/usr/bin/env python3
"""Metrics write - write metric points to SQLite."""
import json
import sys
import time
from pathlib import Path

# Add skill root for constants
_skill_root = Path(__file__).resolve().parent.parent
if str(_skill_root) not in sys.path:
    sys.path.insert(0, str(_skill_root))

from constants import DB_FILENAME
from db.metrics import insert


def _resolve_db_path(params: dict) -> Path:
    p = params.get("db_path")
    if p:
        return Path(p)
    return Path(params.get("workspace_root", "")) / DB_FILENAME


def main() -> None:
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = _resolve_db_path(params)
    name = args.get("name", params.get("name", ""))
    value = float(args.get("value", args.get("value", 0)))
    ts = args.get("timestamp")
    tags = args.get("tags", {})
    if not db_path.exists():
        print(json.dumps({"error": "Database not initialized"}))
        return
    if not name:
        print(json.dumps({"error": "name required"}))
        return
    insert(db_path, name=name, value=value, timestamp=float(ts) if ts else None, tags=tags if tags else None)
    print(json.dumps({"ok": True, "name": name, "value": value}))


if __name__ == "__main__":
    main()
