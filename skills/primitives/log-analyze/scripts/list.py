#!/usr/bin/env python3
"""Log analyze list - list log sessions/dates."""
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
        print(json.dumps({"sessions": [], "dates": []}))
        return
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT DISTINCT session_id FROM logs WHERE session_id IS NOT NULL ORDER BY session_id LIMIT ?",
            (limit,),
        )
        sessions = [r[0] for r in cur.fetchall()]
        cur = conn.execute(
            "SELECT DISTINCT date(timestamp, 'unixepoch') as d FROM logs ORDER BY d DESC LIMIT ?",
            (limit,),
        )
        dates = [r[0] for r in cur.fetchall() if r[0]]
    finally:
        conn.close()
    print(json.dumps({"sessions": sessions, "dates": dates}))


if __name__ == "__main__":
    main()
