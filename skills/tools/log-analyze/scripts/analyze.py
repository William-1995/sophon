#!/usr/bin/env python3
"""Log analyze - aggregate analysis (count by level, time series).

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sqlite3
import sys
import time
from collections import defaultdict

from common.db_utils import resolve_db_path
from defaults import (
    ISO_DATE_YYYY_MM_DD_LEN,
    LOG_ANALYZE_DEFAULT_RANGE_DAYS,
    LOG_ANALYZE_DEFAULT_ROW_LIMIT,
    SECONDS_PER_DAY,
)


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = resolve_db_path(params)
    since = (args.get("since") or "").strip()
    until = (args.get("until") or "").strip()
    limit = int(args.get("limit", params.get("limit", LOG_ANALYZE_DEFAULT_ROW_LIMIT)))

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    if not until:
        until = now.strftime("%Y-%m-%d")
    if not since:
        since_dt = now - timedelta(days=LOG_ANALYZE_DEFAULT_RANGE_DAYS)
        since = since_dt.strftime("%Y-%m-%d")

    if not db_path.exists():
        print(json.dumps({"by_level": {}, "time_series": [], "total": 0}))
        return

    try:
        start_ts = time.mktime(
            time.strptime(since[:ISO_DATE_YYYY_MM_DD_LEN], "%Y-%m-%d")
        )
        end_ts = time.mktime(
            time.strptime(until[:ISO_DATE_YYYY_MM_DD_LEN], "%Y-%m-%d")
        ) + SECONDS_PER_DAY
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
