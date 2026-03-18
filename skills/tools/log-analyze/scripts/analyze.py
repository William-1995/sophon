#!/usr/bin/env python3
"""Log analyze - aggregate analysis (count by level, time series)."""
import json
import sqlite3
import sys
import time
from collections import defaultdict
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
    since = (args.get("since") or "").strip()
    until = (args.get("until") or "").strip()
    limit = int(args.get("limit", params.get("limit", 10000)))

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    if not until:
        until = now.strftime("%Y-%m-%d")
    if not since:
        since_dt = now - timedelta(days=7)
        since = since_dt.strftime("%Y-%m-%d")

    if not db_path.exists():
        print(json.dumps({"by_level": {}, "time_series": [], "total": 0}))
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
            "SELECT level, timestamp FROM logs WHERE timestamp >= ? AND timestamp <= ? ORDER BY timestamp LIMIT ?",
            (start_ts, end_ts, limit),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    by_level = defaultdict(int)
    by_date = defaultdict(int)
    for level, ts in rows:
        by_level[level or "UNKNOWN"] += 1
        try:
            day = time.strftime("%Y-%m-%d", time.localtime(ts))
            by_date[day] += 1
        except (ValueError, OSError):
            pass

    time_series = [{"date": k, "count": v} for k, v in sorted(by_date.items())]
    result: dict = {
        "by_level": dict(by_level),
        "time_series": time_series,
        "total": len(rows),
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
