#!/usr/bin/env python3
"""Metrics query - query metrics from SQLite."""
import json
import sys
import time
from pathlib import Path

from constants import DB_FILENAME
from db.metrics import query as query_metrics


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
    name = args.get("name", params.get("name", ""))
    since = args.get("since")
    until = args.get("until")
    aggregation = args.get("aggregation")
    limit = int(args.get("limit", 1000))
    if not db_path.exists():
        print(json.dumps({"error": "Database not initialized", "data": []}))
        return
    if not name:
        print(json.dumps({"error": "name required", "data": []}))
        return
    if since and isinstance(since, str):
        try:
            since = float(since)
        except ValueError:
            since = None
    if until and isinstance(until, str):
        try:
            until = float(until)
        except ValueError:
            until = None
    data = query_metrics(db_path, name=name, since=since, until=until, aggregation=aggregation, limit=limit)
    for d in data:
        d["date"] = _ts_to_date(d.get("timestamp"))
    result: dict = {"name": name, "data": data}
    if data:
        ts_list = [d.get("timestamp") for d in data if d.get("timestamp") is not None]
        if ts_list:
            result["date_range"] = {
                "min_date": _ts_to_date(min(ts_list)) or "",
                "max_date": _ts_to_date(max(ts_list)) or "",
                "min_timestamp": min(ts_list),
                "max_timestamp": max(ts_list),
            }
    if data and "value" in data[0]:
        x = [d.get("date") or _ts_to_date(d.get("timestamp")) for d in data]
        y = [d.get("value", 0) for d in data]
        result["gen_ui"] = {"type": "line", "payload": {"data": {"x": x, "y": y}}}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
