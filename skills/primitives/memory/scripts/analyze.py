#!/usr/bin/env python3
"""Analyze user messages within a time range.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sqlite3
import sys
from datetime import datetime

from common import resolve_db_path
from defaults import (
    END_OF_DAY_INCLUSIVE_OFFSET_SECONDS,
    ISO_DATE_YYYY_MM_DD_LEN,
    MEMORY_USER_CONTENT_SNIPPET_MAX_CHARS,
)
from _scope import resolve_scoped_session_ids


def _parse_time(value: str, end_of_day: bool = False) -> float:
    """Accept YYYY-MM-DD or Unix timestamp. end_of_day shifts to 23:59:59 of that day."""
    try:
        return float(value)
    except ValueError:
        ts = datetime.strptime(
            value[:ISO_DATE_YYYY_MM_DD_LEN], "%Y-%m-%d"
        ).timestamp()
        return ts + END_OF_DAY_INCLUSIVE_OFFSET_SECONDS if end_of_day else ts


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = resolve_db_path(params)
    since = str(args.get("since", "")).strip()
    until = str(args.get("until", "")).strip()

    if not db_path.exists():
        print(json.dumps({"error": "Database not found"}))
        return
    if not since or not until:
        print(json.dumps({"error": "since and until are required"}))
        return

    try:
        since_ts = _parse_time(since)
        until_ts = _parse_time(until, end_of_day=True)
    except Exception as exc:
        print(json.dumps({"error": f"Invalid date format: {exc}"}))
        return

    scope_ids = resolve_scoped_session_ids(params, params.get("session_id"))
    if isinstance(scope_ids, list) and scope_ids:
        placeholders = ",".join("?" * len(scope_ids))
        sql = (
            f"SELECT session_id, content, created_at FROM memory_long_term "
            f"WHERE role = 'user' AND created_at >= ? AND created_at <= ? "
            f"AND session_id IN ({placeholders}) ORDER BY created_at"
        )
        qargs: tuple = (since_ts, until_ts) + tuple(scope_ids)
    else:
        sql = (
            "SELECT session_id, content, created_at FROM memory_long_term "
            "WHERE role = 'user' AND created_at >= ? AND created_at <= ? ORDER BY created_at"
        )
        qargs = (since_ts, until_ts)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, qargs).fetchall()
    conn.close()

    messages = [
        {
            "session_id": r["session_id"],
            "time": datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d %H:%M"),
            "content": r["content"][:MEMORY_USER_CONTENT_SNIPPET_MAX_CHARS],
        }
        for r in rows
        if not (r["content"] or "").startswith("[Background] ")
    ]
    lines = [f"count={len(messages)} since={datetime.fromtimestamp(since_ts).strftime('%Y-%m-%d')} until={datetime.fromtimestamp(until_ts).strftime('%Y-%m-%d')}"]
    lines.extend(f"[{m['time']}] {m['content']}" for m in messages)
    print(json.dumps({
        "count": len(messages),
        "since": datetime.fromtimestamp(since_ts).strftime("%Y-%m-%d"),
        "until": datetime.fromtimestamp(until_ts).strftime("%Y-%m-%d"),
        "messages": messages,
        "observation": "\n".join(lines),
    }))


if __name__ == "__main__":
    main()
