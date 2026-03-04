#!/usr/bin/env python3
"""Metrics query - query metrics from SQLite."""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from constants import DB_FILENAME
from db.metrics import query as query_metrics

# Auto-bucket when raw point count exceeds this threshold
_AUTO_BUCKET_THRESHOLD = 100


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


def _bucket_by_hour(data: list[dict]) -> list[dict]:
    """Average data points into hourly buckets to keep chart readable."""
    buckets: dict[int, list[float]] = defaultdict(list)
    for d in data:
        ts = d.get("timestamp")
        val = d.get("value")
        if ts is not None and val is not None:
            hour_key = int(ts) // 3600 * 3600
            buckets[hour_key].append(float(val))
    return [
        {
            "timestamp": hour_ts,
            "value": round(sum(vals) / len(vals), 2),
            "date": time.strftime("%m-%d %H:00", time.localtime(hour_ts)),
        }
        for hour_ts, vals in sorted(buckets.items())
    ]


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
        if "date" not in d:
            d["date"] = _ts_to_date(d.get("timestamp"))

    # Auto-aggregate into hourly buckets when too many raw points
    if len(data) > _AUTO_BUCKET_THRESHOLD and not aggregation:
        data = _bucket_by_hour(data)

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
        dr = result.get("date_range", {})
        vals = [d["value"] for d in data if "value" in d]
        summary = (
            f"metric={name} points={len(data)} "
            f"min={min(vals):.1f} max={max(vals):.1f} avg={sum(vals)/len(vals):.1f} "
            f"from={dr.get('min_date', '')} to={dr.get('max_date', '')}"
        )
        rows = [f"[{d.get('date', '')}] {d['value']:.1f}" for d in data if "value" in d]
        result["observation"] = summary + "\n" + "\n".join(rows)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
