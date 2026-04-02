#!/usr/bin/env python3
"""Log analyze list - list log sessions/dates.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sqlite3
import sys
from pathlib import Path

from common.db_utils import resolve_db_path

from defaults import DB_FILENAME


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = resolve_db_path(params)
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
