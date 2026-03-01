#!/usr/bin/env python3
"""Time convert - convert timestamp between timezones."""
import json
import sys
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None


def _parse_timestamp(ts: str):
    if not ts:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(ts[:19], fmt)
        except (ValueError, TypeError):
            continue
    try:
        return datetime.strptime(ts[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _to_tz(dt: datetime, tz_name: str) -> datetime:
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=timezone.utc)
    tz_lower = (tz_name or "").lower()
    if tz_lower in ("local", ""):
        return dt.astimezone()
    if ZoneInfo:
        return dt.astimezone(ZoneInfo(tz_name))
    if tz_name.upper() == "UTC":
        return dt.astimezone(timezone.utc)
    return dt


def main() -> None:
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    ts = (args.get("timestamp") or "").strip()
    from_tz = (args.get("from_tz") or "UTC").strip()
    to_tz = (args.get("to_tz") or "local").strip()
    if not ts:
        print(json.dumps({"error": "timestamp is required"}))
        return
    dt = _parse_timestamp(ts)
    if not dt:
        print(json.dumps({"error": "Invalid timestamp format"}))
        return
    if not dt.tzinfo:
        if from_tz.upper() == "UTC":
            dt = dt.replace(tzinfo=timezone.utc)
        elif ZoneInfo:
            dt = dt.replace(tzinfo=ZoneInfo(from_tz))
    try:
        result = _to_tz(dt, to_tz)
        print(json.dumps({
            "original": ts,
            "from_timezone": from_tz,
            "to_timezone": to_tz,
            "result": result.isoformat(),
            "formatted": result.strftime("%Y-%m-%d %H:%M:%S"),
        }))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main()
