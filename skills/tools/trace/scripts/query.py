#!/usr/bin/env python3
"""Trace query - query traces from SQLite.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sys
import time
from pathlib import Path

from common.db_utils import resolve_db_path



def _ts_to_date(ts) -> str | None:
    """Format Unix epoch seconds as local ``YYYY-MM-DD HH:MM:SS``.

    Args:
        ts: Epoch seconds or numeric string; ``None`` yields ``None``.

    Returns:
        str | None: Formatted time, or ``None`` if invalid.
    """
    if ts is None:
        return None
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(float(ts))))
    except (TypeError, ValueError, OSError):
        return None


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = resolve_db_path(params)
    session_id = args.get("session_id", params.get("session_id"))
    if session_id is not None and isinstance(session_id, str):
        session_id = session_id.strip() or None
    limit = int(args.get("limit", params.get("limit", 1000)))
    if not db_path.exists():
        print(json.dumps({"error": "Database not initialized", "traces": []}))
        return
    conn = __import__("sqlite3").connect(str(db_path))
    conn.row_factory = __import__("sqlite3").Row
    try:
        if session_id:
            cur = conn.execute(
                "SELECT id, session_id, timestamp, skill, action, tokens, result_preview FROM traces WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit),
            )
        else:
            cur = conn.execute(
                "SELECT id, session_id, timestamp, skill, action, tokens, result_preview FROM traces ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    for r in rows:
        r["date"] = _ts_to_date(r.get("timestamp"))
    print(json.dumps({"traces": rows, "scope": "session" if session_id else "global"}))


if __name__ == "__main__":
    main()
