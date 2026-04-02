#!/usr/bin/env python3
"""
RLM-style memory exploration: session index and suggested next memory tools.

Returns session metadata and a short tool map so the model can orient before search/analyze.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from common import resolve_db_path
from _scope import resolve_scoped_session_ids

# Max session rows to include in explore output (truncated with "...and N more" if exceeded)
EXPLORE_MAX_SESSIONS_DISPLAY = 100


def _load_session_index(db_path: Path, scope_session_ids: list[str] | None = None) -> dict:
    """Load a lightweight session index from ``memory_long_term``.

    Args:
        db_path (Path): SQLite path.
        scope_session_ids (list[str] | None): When set, restrict to these sessions.

    Returns:
        dict: Maps ``session_id`` to ``message_count``, ``first_ts``, ``last_ts`` keys.
    """
    conn = sqlite3.connect(str(db_path))
    if scope_session_ids:
        placeholders = ",".join("?" * len(scope_session_ids))
        sql = (
            f"SELECT session_id, COUNT(*) as cnt, MIN(created_at) as first_ts, MAX(created_at) as last_ts "
            f"FROM memory_long_term WHERE session_id IN ({placeholders}) "
            f"GROUP BY session_id ORDER BY last_ts DESC"
        )
        rows = conn.execute(sql, scope_session_ids).fetchall()
    else:
        rows = conn.execute(
            "SELECT session_id, COUNT(*) as cnt, MIN(created_at) as first_ts, MAX(created_at) as last_ts "
            "FROM memory_long_term GROUP BY session_id ORDER BY last_ts DESC"
        ).fetchall()
    conn.close()
    return {
        r[0]: {"message_count": r[1], "first_ts": r[2], "last_ts": r[3]}
        for r in rows
    }


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = resolve_db_path(params)
    query = str(args.get("query", "")).strip()
    session_hint = args.get("session_hint")
    max_depth = int(args.get("max_depth", 3))

    if not db_path.exists():
        print(json.dumps({"error": "Database not found", "db_path": str(db_path)}))
        return

    scope_ids = resolve_scoped_session_ids(params, params.get("session_id"))
    index = _load_session_index(db_path, scope_session_ids=scope_ids)
    total_messages = sum(v["message_count"] for v in index.values())
    next_steps = (
        "Use memory.search(keyword) for topic search, "
        "memory.analyze(since, until) for time range, "
        "memory.detail(session_id) for full session content."
    )
    lines = [f"sessions={len(index)} total_messages={total_messages}", next_steps]
    for sid, meta in list(index.items())[:EXPLORE_MAX_SESSIONS_DISPLAY]:
        first = datetime.fromtimestamp(meta["first_ts"]).strftime("%m-%d %H:%M") if meta.get("first_ts") else ""
        last = datetime.fromtimestamp(meta["last_ts"]).strftime("%m-%d %H:%M") if meta.get("last_ts") else ""
        lines.append(f"  {sid} | {meta['message_count']} msgs | {first} -> {last}")
    if len(index) > EXPLORE_MAX_SESSIONS_DISPLAY:
        lines.append(f"  ... and {len(index) - EXPLORE_MAX_SESSIONS_DISPLAY} more sessions")

    print(json.dumps({
        "status": "ready",
        "sessions_loaded": len(index),
        "total_messages": total_messages,
        "session_index": index,
        "session_hint": session_hint,
        "query": query,
        "max_depth": max_depth,
        "next_steps": next_steps,
        "observation": "\n".join(lines),
    }))


if __name__ == "__main__":
    main()
