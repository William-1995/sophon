"""Trace operations - insert execution traces."""
import time
from pathlib import Path

from constants import EXECUTOR_TRACE_PREVIEW_LEN
from db.schema import get_connection


def query_range(
    db_path: Path,
    session_id: str,
    start_at: float,
    end_at: float,
    limit: int = 100,
) -> list[dict]:
    """Query traces in a time range for a session.

    Args:
        db_path: Path to SQLite database.
        session_id: Session ID to filter.
        start_at: Start timestamp (inclusive).
        end_at: End timestamp (inclusive).
        limit: Max rows to return.

    Returns:
        List of trace dicts with skill, action, result_preview, timestamp, etc.
    """
    import sqlite3
    if not db_path or not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            """
            SELECT session_id, timestamp, skill, action, tokens, result_preview, metadata
            FROM traces
            WHERE session_id = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp
            LIMIT ?
            """,
            (session_id, start_at, end_at, limit),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def insert(
    db_path: Path,
    session_id: str,
    skill: str,
    action: str,
    tokens: int = 0,
    result_preview: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Insert trace entry."""
    import json
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO traces (session_id, timestamp, skill, action, tokens, result_preview, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                time.time(),
                skill,
                action,
                tokens,
                (
                    result_preview[:EXECUTOR_TRACE_PREVIEW_LEN]
                    if result_preview
                    else None
                ),
                json.dumps(metadata) if metadata else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()
