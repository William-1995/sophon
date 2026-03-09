#!/usr/bin/env python3
"""
Memory Search - Search conversation memory with FTS5.

Provides full-text search over conversation memory with:
- FTS5 (full-text search) or LIKE-based fallback
- Date range filtering
- Session scoping
- Duplicate removal

Uses memory_fts virtual table for fast full-text search when available.

Example:
    $ echo '{"query": "machine learning", "limit": 50}' | python search.py
    {"results": [{"id": 1, "role": "user", "content": "...", "date": "2024-01-01 12:00:00"}, ...]}
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

# Add skill root first (for constants), then project root (for common via skills/primitives)
_skill_root = Path(__file__).resolve().parent.parent
_root = _skill_root.parent.parent.parent
for p in (_skill_root, _root):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from common import resolve_db_path, ts_to_date, safe_db_connection
from common.time_utils import parse_date_to_ts, SECONDS_PER_DAY
from constants import DEFAULT_QUERY_LIMIT, SQL_DATE_FORMAT


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Pattern to filter out background task markers
BACKGROUND_MARKER = "[Background] "

# Minimum query length for FTS5
MIN_FTS_QUERY_LENGTH = 1


# ---------------------------------------------------------------------------
# Private API
# ---------------------------------------------------------------------------

def _build_fts5_query(query_str: str) -> str:
    """Build FTS5 MATCH expression from query string.

    Converts query into AND-separated quoted tokens.
    Removes double quotes from tokens to prevent syntax errors.

    Args:
        query_str: Raw search query.

    Returns:
        FTS5 MATCH expression or empty string.

    Example:
        >>> _build_fts5_query("hello world")
        '"hello" AND "world"'
    """
    if not query_str:
        return ""

    tokens = [t.strip() for t in re.split(r"\s+", query_str) if t.strip()]
    if not tokens:
        return ""

    escaped = [t.replace('"', '') for t in tokens]
    return " AND ".join(f'"{t}"' for t in escaped)


def _build_date_filter(
    date_range: dict | None,
    table_prefix: str = "",
) -> tuple[str, list]:
    """Build SQL date range filter clause.

    Args:
        date_range: Dict with "start" and/or "end" dates (YYYY-MM-DD).
        table_prefix: Optional table alias prefix (e.g., "m.").

    Returns:
        Tuple of (sql_extra, params).
    """
    if not date_range or not isinstance(date_range, dict):
        return "", []

    sql_extra = ""
    params: list = []
    col = f"{table_prefix}created_at" if table_prefix else "created_at"

    start = (date_range.get("start") or "")[:10]
    end = (date_range.get("end") or "")[:10]

    if start:
        try:
            ts = parse_date_to_ts(start, SQL_DATE_FORMAT)
            if ts:
                params.append(ts)
                sql_extra += f" AND {col} >= ?"
        except ValueError:
            pass

    if end:
        try:
            ts = parse_date_to_ts(end, SQL_DATE_FORMAT)
            if ts:
                params.append(ts + SECONDS_PER_DAY)
                sql_extra += f" AND {col} < ?"
        except ValueError:
            pass

    return sql_extra, params


def _is_background_message(role: str, content: str | None) -> bool:
    """Check if message is a background task marker.

    Args:
        role: Message role.
        content: Message content.

    Returns:
        True if this is a background task placeholder.
    """
    return bool(role == "user" and content and content.startswith(BACKGROUND_MARKER))


def _build_memory_row(row: tuple) -> dict:
    """Build memory row dict from database result.

    Args:
        row: Database row tuple (id, session_id, role, content, created_at).

    Returns:
        Memory row dict with formatted date.
    """
    return {
        "id": row[0],
        "session_id": row[1],
        "role": row[2],
        "content": row[3] or "",
        "created_at": row[4],
        "date": ts_to_date(row[4]),
    }


def _search_session(
    conn: sqlite3.Connection,
    session_id: str,
    query_str: str,
    fts_expr: str,
    date_sql: str,
    date_params: list,
    limit: int,
) -> list[dict]:
    """Search within specific session.

    Args:
        conn: Database connection.
        session_id: Session ID to search.
        query_str: Raw query string.
        fts_expr: FTS5 expression.
        date_sql: Date filter SQL.
        date_params: Date filter parameters.
        limit: Maximum results.

    Returns:
        List of memory rows.
    """
    table_prefix = "m." if fts_expr else ""
    params: list = []

    if fts_expr:
        sql = (
            f"SELECT m.id, m.session_id, m.role, m.content, m.created_at "
            f"FROM memory_long_term m "
            f"JOIN memory_fts ON memory_fts.rowid = m.id AND memory_fts MATCH ? "
            f"WHERE m.session_id = ? {date_sql}"
        )
        params = [fts_expr, session_id] + date_params
    else:
        like_val = f"%{query_str}%" if query_str else "%%"
        sql = (
            f"SELECT id, session_id, role, content, created_at "
            f"FROM memory_long_term "
            f"WHERE content LIKE ? AND session_id = ? {date_sql}"
        )
        params = [like_val, session_id] + date_params

    sql += f" ORDER BY {table_prefix}created_at DESC LIMIT ?"
    params.append(limit)

    cur = conn.execute(sql, params)
    return [
        _build_memory_row(r)
        for r in cur.fetchall()
        if not _is_background_message(r[2], r[3])
    ]


def _search_all(
    conn: sqlite3.Connection,
    query_str: str,
    fts_expr: str,
    date_sql: str,
    date_params: list,
    limit: int,
    exclude_ids: set[int],
) -> list[dict]:
    """Search all sessions, excluding already found IDs.

    Args:
        conn: Database connection.
        query_str: Raw query string.
        fts_expr: FTS5 expression.
        date_sql: Date filter SQL.
        date_params: Date filter parameters.
        limit: Maximum results.
        exclude_ids: Set of IDs to exclude.

    Returns:
        List of memory rows.
    """
    table_prefix = "m." if fts_expr else ""
    params: list = []

    if fts_expr:
        sql = (
            f"SELECT m.id, m.session_id, m.role, m.content, m.created_at "
            f"FROM memory_long_term m "
            f"JOIN memory_fts ON memory_fts.rowid = m.id AND memory_fts MATCH ? "
            f"WHERE 1=1 {date_sql}"
        )
        params = [fts_expr] + date_params
    else:
        like_val = f"%{query_str}%" if query_str else "%%"
        sql = (
            f"SELECT id, session_id, role, content, created_at "
            f"FROM memory_long_term "
            f"WHERE content LIKE ? {date_sql}"
        )
        params = [like_val] + date_params

    if exclude_ids:
        placeholders = ",".join("?" * len(exclude_ids))
        sql += f" AND {table_prefix}id NOT IN ({placeholders})"
        params.extend(list(exclude_ids))

    sql += f" ORDER BY {table_prefix}created_at DESC LIMIT ?"
    params.append(limit)

    cur = conn.execute(sql, params)
    results = []
    for r in cur.fetchall():
        if _is_background_message(r[2], r[3]):
            continue
        row = _build_memory_row(r)
        if row["id"] not in exclude_ids:
            results.append(row)

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def main() -> None:
    """Main entry point for memory search operation."""
    # Parse input
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)

    # Resolve database path
    db_path = resolve_db_path(params)

    # Extract search parameters
    query_str = (args.get("query") or params.get("query", "")).strip()
    limit = int(
        args.get("top_k")
        or args.get("limit")
        or params.get("limit")
        or params.get("_memory_search_default_limit")
        or DEFAULT_QUERY_LIMIT
    )
    session_id = args.get("session_id") or params.get("_executor_session_id")

    # Normalize date range
    date_range = args.get("date_range") or params.get("date_range")
    if isinstance(date_range, (list, tuple)) and len(date_range) >= 2:
        date_range = {
            "start": str(date_range[0])[:10],
            "end": str(date_range[1])[:10],
        }

    # Check database exists
    if not db_path.exists():
        print(json.dumps({"results": []}))
        return

    # Build FTS5 expression
    use_fts = bool(query_str)
    fts_expr = _build_fts5_query(query_str) if use_fts else ""

    # Build date filter (ensure date_range is dict or None)
    table_prefix = "m." if fts_expr else ""
    normalized_date_range = date_range if isinstance(date_range, dict) else None
    date_sql, date_params = _build_date_filter(normalized_date_range, table_prefix)

    # Execute search
    with safe_db_connection(db_path) as conn:
        rows: list[dict] = []
        seen_ids: set[int] = set()

        # First: search within session if specified
        if session_id:
            session_results = _search_session(
                conn, session_id, query_str, fts_expr,
                date_sql, date_params, limit
            )
            for row in session_results:
                seen_ids.add(row["id"])
                rows.append(row)

        # Second: search all other sessions if needed
        if len(rows) < limit:
            remaining = limit - len(rows)
            other_results = _search_all(
                conn, query_str, fts_expr,
                date_sql, date_params, remaining,
                seen_ids
            )
            rows.extend(other_results)

    # Sort and limit results
    rows = sorted(rows, key=lambda x: x["created_at"] or 0, reverse=True)[:limit]

    # Output results
    print(json.dumps({"results": rows}))


if __name__ == "__main__":
    main()
