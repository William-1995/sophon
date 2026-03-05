"""Analyze user messages within a time range.

Returns only user-role messages in a compact flat format so the caller can
enumerate them without further truncation or JSON overhead.
"""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

_CONTENT_PREVIEW = 200


def _parse_time(value: str, end_of_day: bool = False) -> float:
    """Accept YYYY-MM-DD or Unix timestamp. end_of_day shifts to 23:59:59 of that day."""
    try:
        return float(value)
    except ValueError:
        ts = datetime.strptime(value[:10], "%Y-%m-%d").timestamp()
        return ts + 86399 if end_of_day else ts


def main() -> None:
    params = json.loads(sys.stdin.read())
    db_path = params.get("db_path")
    since = str(params.get("since", "")).strip()
    until = str(params.get("until", "")).strip()

    if not db_path or not Path(db_path).exists():
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

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT session_id, content, created_at FROM memory_long_term "
        "WHERE role = 'user' AND created_at >= ? AND created_at <= ? ORDER BY created_at",
        (since_ts, until_ts),
    ).fetchall()
    conn.close()

    messages = [
        {
            "session_id": r["session_id"],
            "time": datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d %H:%M"),
            "content": r["content"][:_CONTENT_PREVIEW],
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
