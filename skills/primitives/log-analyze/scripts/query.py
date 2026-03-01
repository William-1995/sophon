#!/usr/bin/env python3
"""Log analyze query - query logs from SQLite."""
import json
import re
import sys
import time
from pathlib import Path

from constants import DB_FILENAME
from db.logs import query as query_logs


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
    db_path = _resolve_db_path(params)
    if not db_path.exists():
        print(json.dumps({"error": "Database not initialized", "logs": []}))
        return
    since = params.get("since")
    until = params.get("until")
    level_raw = params.get("level") or params.get("arguments", {}).get("level")
    if isinstance(level_raw, str) and level_raw:
        level = ",".join(l.strip().upper() for l in level_raw.split(",") if l.strip())
    else:
        level = level_raw
    args = params.get("arguments", params)
    session_id = args.get("session_id", params.get("session_id"))
    keyword = (params.get("keyword") or args.get("keyword") or "").strip()
    regex_str = (params.get("regex") or args.get("regex") or "").strip()
    exclude_keyword = (params.get("exclude_keyword") or args.get("exclude_keyword") or "").strip()
    limit = int(args.get("limit", params.get("limit", 1000)))
    if since and isinstance(since, str):
        try:
            since = time.mktime(time.strptime(since[:10], "%Y-%m-%d"))
        except ValueError:
            since = None
    if until and isinstance(until, str):
        try:
            until = time.mktime(time.strptime(until[:10], "%Y-%m-%d")) + 86400
        except ValueError:
            until = None
    fetch_limit = limit * 4 if (keyword or regex_str or exclude_keyword) else limit
    rows = query_logs(db_path, since=since, until=until, level=level, session_id=session_id, limit=fetch_limit)
    if keyword:
        kw = keyword.lower()
        rows = [r for r in rows if kw in (str(r.get("message", "")) + str(r.get("metadata", ""))).lower()]
    if exclude_keyword:
        ex = exclude_keyword.lower()
        rows = [r for r in rows if ex not in (str(r.get("message", "")) + str(r.get("metadata", ""))).lower()]
    if regex_str:
        try:
            pat = re.compile(regex_str)
            rows = [r for r in rows if pat.search(str(r.get("message", "")) + str(r.get("metadata", "")))]
        except re.error:
            pass
    rows = rows[:limit]
    for r in rows:
        r["date"] = _ts_to_date(r.get("timestamp"))
    print(json.dumps({"logs": rows, "count": len(rows)}))


if __name__ == "__main__":
    main()
