#!/usr/bin/env python3
"""
Log Analyze Query - Query logs from SQLite.

Queries application logs with filtering by:
- Time range (since/until)
- Log level (INFO, ERROR, DEBUG, etc.)
- Session ID
- Keyword (substring search)
- Regex pattern

Example:
    $ echo '{"level": "ERROR", "limit": 50}' | python query.py
    {"logs": [...], "count": 50}
"""

import json
import re
import sys
import time
from pathlib import Path

# Add skill root first (for constants), then project root (for common)
_skill_root = Path(__file__).resolve().parent.parent
_root = _skill_root.parent.parent.parent
for p in (_skill_root, _root):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from common import resolve_db_path, ts_to_date
from db.logs import query as query_logs


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

DEFAULT_LIMIT = 1000
DATE_FORMAT = "%Y-%m-%d"


# ---------------------------------------------------------------------------
# Private API
# ---------------------------------------------------------------------------

def _parse_level(level_raw: str | None) -> str | None:
    """Parse and normalize level filter.

    Args:
        level_raw: Raw level string (may contain commas).

    Returns:
        Normalized level string or None.
    """
    if not level_raw or not isinstance(level_raw, str):
        return level_raw

    return ",".join(
        level.strip().upper()
        for level in level_raw.split(",")
        if level.strip()
    )


def _parse_timestamp(ts_str: str | None, is_end: bool = False) -> float | None:
    """Parse timestamp string to Unix timestamp.

    Args:
        ts_str: Timestamp string (YYYY-MM-DD format).
        is_end: Whether this is an end timestamp (adds 1 day).

    Returns:
        Unix timestamp or None if invalid.
    """
    if not ts_str or not isinstance(ts_str, str):
        return None

    try:
        ts = time.mktime(time.strptime(ts_str[:10], DATE_FORMAT))
        if is_end:
            ts += 86400  # Add one day
        return ts
    except ValueError:
        return None


def _matches_filters(
    row: dict,
    keyword: str,
    exclude_keyword: str,
    regex_pattern: re.Pattern | None,
) -> bool:
    """Check if log row matches all filters.

    Args:
        row: Log row dict.
        keyword: Keyword to include.
        exclude_keyword: Keyword to exclude.
        regex_pattern: Compiled regex pattern.

    Returns:
        True if row matches all filters.
    """
    text = (str(row.get("message", "")) + str(row.get("metadata", ""))).lower()

    if keyword and keyword.lower() not in text:
        return False

    if exclude_keyword and exclude_keyword.lower() in text:
        return False

    if regex_pattern and not regex_pattern.search(text):
        return False

    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def main() -> None:
    """Main entry point for log query operation."""
    # Parse input
    params = json.loads(sys.stdin.read())

    # Resolve database path
    db_path = resolve_db_path(params)

    # Check database exists
    if not db_path.exists():
        print(json.dumps({"error": "Database not initialized", "logs": []}))
        return

    # Extract parameters
    args = params.get("arguments", params)
    since = _parse_timestamp(params.get("since"))
    until = _parse_timestamp(params.get("until"), is_end=True)

    level_raw = params.get("level") or args.get("level")
    level = _parse_level(level_raw)

    session_id = args.get("session_id", params.get("session_id"))
    keyword = (params.get("keyword") or args.get("keyword") or "").strip()
    regex_str = (params.get("regex") or args.get("regex") or "").strip()
    exclude_keyword = (params.get("exclude_keyword") or args.get("exclude_keyword") or "").strip()
    limit = int(args.get("limit", params.get("limit", DEFAULT_LIMIT)))

    # Compile regex if provided
    regex_pattern: re.Pattern | None = None
    if regex_str:
        try:
            regex_pattern = re.compile(regex_str)
        except re.error:
            regex_pattern = None

    # Calculate fetch limit (fetch more if filtering)
    fetch_limit = limit * 4 if (keyword or regex_pattern or exclude_keyword) else limit

    # Query logs
    rows = query_logs(
        db_path, since=since, until=until, level=level,
        session_id=session_id, limit=fetch_limit
    )

    # Apply filters
    rows = [
        r for r in rows
        if _matches_filters(r, keyword, exclude_keyword, regex_pattern)
    ]

    # Limit results
    rows = rows[:limit]

    # Add date formatting
    for r in rows:
        r["date"] = ts_to_date(r.get("timestamp"))

    print(json.dumps({"logs": rows, "count": len(rows)}))


if __name__ == "__main__":
    main()
