#!/usr/bin/env python3
"""Trace list - list recent trace sessions.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sqlite3
import sys
from pathlib import Path

from common.db_utils import resolve_db_path



def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = resolve_db_path(params)
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
