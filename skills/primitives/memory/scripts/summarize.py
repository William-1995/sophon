#!/usr/bin/env python3
"""Memory summarize - summarize memory over a period."""
import json
import sqlite3
import sys
import time
from pathlib import Path

from constants import DB_FILENAME


def _ts_to_date(ts) -> str | None:
    """Format Unix timestamp to YYYY-MM-DD HH:MM:SS."""
    if ts is None:
        return None
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(float(ts))))
    except (TypeError, ValueError, OSError):
        return None


def _resolve_db_path(params: dict) -> Path:
    p = params.get("db_path")
    if p:
        return Path(p)
    return Path(params.get("workspace_root", "")) / DB_FILENAME


def main() -> None:
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = _resolve_db_path(params)
    since = (args.get("since") or "").strip()
    until = (args.get("until") or "").strip()
    focus = (args.get("focus") or "").strip()

    if not since or not until:
        print(json.dumps({"error": "since and until are required"}))
        return
    if not db_path.exists():
        print(json.dumps({"results": [], "summary": "No memory data"}))
        return

    try:
        start_ts = time.mktime(time.strptime(since[:10], "%Y-%m-%d"))
        end_ts = time.mktime(time.strptime(until[:10], "%Y-%m-%d")) + 86400
    except ValueError:
        print(json.dumps({"error": "Invalid date format, use YYYY-MM-DD"}))
        return

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "SELECT session_id, role, content, created_at FROM memory_long_term WHERE created_at >= ? AND created_at < ? ORDER BY created_at",
            (start_ts, end_ts),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    contents = []
    for r in rows:
        session_id, role, content, created_at = r[0], r[1], r[2], r[3]
        if role == "user" and (content or "").startswith("[Background] "):
            continue
        if focus and focus.lower() not in (content or "").lower():
            continue
        contents.append({"session_id": session_id, "role": role, "content": (content or "")[:500], "created_at": created_at, "date": _ts_to_date(created_at)})

    summary = f"Found {len(contents)} messages from {since} to {until}"
    if focus:
        summary += f" (focus: {focus})"
    print(json.dumps({"results": contents, "count": len(contents), "summary": summary}))


if __name__ == "__main__":
    main()
