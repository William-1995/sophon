#!/usr/bin/env python3
"""Trace list - list recent trace sessions."""
import json
import sqlite3
import sys
from pathlib import Path

# Add skill root for constants
_skill_root = Path(__file__).resolve().parent.parent
if str(_skill_root) not in sys.path:
    sys.path.insert(0, str(_skill_root))

from constants import DB_FILENAME


def _resolve_db_path(params: dict) -> Path:
    p = params.get("db_path")
    if p:
        return Path(p)
    return Path(params.get("workspace_root", "")) / DB_FILENAME


def main() -> None:
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = _resolve_db_path(params)
    limit = int(args.get("limit", params.get("limit", 100)))
    if not db_path.exists():
        print(json.dumps({"sessions": []}))
        return
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "SELECT session_id FROM traces GROUP BY session_id ORDER BY MAX(timestamp) DESC LIMIT ?",
            (limit,),
        )
        sessions = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    print(json.dumps({"sessions": sessions}))


if __name__ == "__main__":
    main()
