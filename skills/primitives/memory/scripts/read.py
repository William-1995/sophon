#!/usr/bin/env python3
"""Memory read - read memory by date or session."""
import json
import sqlite3
import sys
import time
from pathlib import Path

# Add skill root for constants
_skill_root = Path(__file__).resolve().parent.parent
if str(_skill_root) not in sys.path:
    sys.path.insert(0, str(_skill_root))

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
    date_str = args.get("date", "")
    session_id = args.get("session_id") or params.get("_executor_session_id") or ""
    limit = int(args.get("limit", 50))
    order = (args.get("order") or "asc").lower()
    order_desc = order in ("desc", "newest")
    if not db_path.exists():
        print(json.dumps({"results": []}))
        return
    conn = sqlite3.connect(str(db_path))
    try:
        if session_id:
            order_sql = "DESC" if order_desc else "ASC"
            cur = conn.execute(
                f"SELECT role, content, created_at FROM memory_long_term WHERE session_id = ? ORDER BY created_at {order_sql} LIMIT ?",
                (session_id, limit),
            )
        elif date_str:
            order_sql = "DESC" if order_desc else "ASC"
            if date_str in ("today", "yesterday"):
                from datetime import datetime, timedelta, timezone
                now = datetime.now(timezone.utc)
                if date_str == "today":
                    start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                else:
                    start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                end = time.time() + 86400
            else:
                try:
                    start = time.mktime(time.strptime(date_str[:10], "%Y-%m-%d"))
                    end = start + 86400
                except ValueError:
                    start, end = 0, time.time() + 86400
            cur = conn.execute(
                f"SELECT session_id, role, content, created_at FROM memory_long_term WHERE created_at >= ? AND created_at < ? ORDER BY created_at {order_sql} LIMIT ?",
                (start, end, limit),
            )
        else:
            order_sql = "DESC" if order_desc else "ASC"
            cur = conn.execute(
                f"SELECT session_id, role, content, created_at FROM memory_long_term ORDER BY created_at {order_sql} LIMIT ?",
                (limit,),
            )
        rows = []
        for r in cur.fetchall():
            r = list(r)
            ts = r[3] if len(r) >= 4 else r[2] if len(r) >= 3 else None
            rows.append({
                "session_id": r[0] if len(r) >= 4 else None,
                "role": r[1] if len(r) >= 4 else r[0],
                "content": (r[2] if len(r) >= 4 else r[1]) or "",
                "created_at": ts,
                "date": _ts_to_date(ts),
            })
    finally:
        conn.close()
    print(json.dumps({"results": rows}))


if __name__ == "__main__":
    main()
