#!/usr/bin/env python3
"""Time calculate - natural language to date range.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from constants import ISO_DATE_YYYY_MM_DD_LEN


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    expr = (args.get("expression") or args.get("expr", "")).strip().lower()
    base = (args.get("base_date") or "").strip()[:ISO_DATE_YYYY_MM_DD_LEN]

    if not expr:
        print(json.dumps({"error": "expression required"}))
        return

    if base:
        try:
            now = datetime.strptime(base, "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=12, minute=0, second=0, microsecond=0)
        except ValueError:
            now = datetime.now(timezone.utc)
    else:
        now = datetime.now(timezone.utc)
    since = until = now
    if "today" in expr:
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        until = now
    elif "yesterday" in expr:
        since = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        until = since + timedelta(days=1)
    else:
        m = re.search(r"(\d+)\s*(h|hour|hours|d|day|days)", expr)
        if m:
            n = int(m.group(1))
            unit = m.group(2)[0]
            if unit == "h":
                since = now - timedelta(hours=n)
            else:
                since = now - timedelta(days=n)
            until = now

    print(json.dumps({
        "expression": expr,
        "since": since.isoformat(),
        "until": until.isoformat(),
    }))


if __name__ == "__main__":
    main()
