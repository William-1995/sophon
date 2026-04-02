#!/usr/bin/env python3
"""Time format - format timestamp to string.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sys
from datetime import datetime, timezone


def _parse_timestamp(ts: str):
    if not ts:
        return None
    if str(ts).lower() == "now":
        return datetime.now(timezone.utc)
    s = str(ts).strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _normalize_fmt(fmt: str) -> str:
    """Map YYYY/MM/DD style to strftime."""
    return (
        fmt.replace("YYYY", "%Y")
        .replace("MM", "%m")
        .replace("DD", "%d")
        .replace("HH", "%H")
        .replace("mm", "%M")
        .replace("ss", "%S")
    )


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    ts = (args.get("timestamp") or args.get("ts") or args.get("original", "")).strip()
    fmt = (args.get("format") or "%Y-%m-%d %H:%M:%S").strip()
    if not ts:
        print(json.dumps({"error": "timestamp is required"}))
        return
    dt = _parse_timestamp(ts)
    if not dt:
        print(json.dumps({"error": "Invalid timestamp format"}))
        return
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        result = dt.strftime(_normalize_fmt(fmt))
        print(json.dumps({"original": ts, "format": fmt, "result": result}))
    except ValueError as e:
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main()
