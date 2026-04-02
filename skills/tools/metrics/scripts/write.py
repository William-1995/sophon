#!/usr/bin/env python3
"""Metrics write - write metric points to SQLite.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sys
from pathlib import Path

from common.db_utils import resolve_db_path

from db.metrics import insert


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = resolve_db_path(params)
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
