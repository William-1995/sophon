"""
Emotion segments - insert and query emotion/session summaries.

Stores weighted user+system summaries per time window for emotion awareness.
"""

import sqlite3
import time
from pathlib import Path
from typing import Any

from db.schema import get_connection


def _conn(db_path: Path | None):
    """Connect via db_path when provided (ensures we write to the correct DB)."""
    if db_path is not None and str(db_path).strip() and db_path.exists():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn
    return get_connection()


def insert(
    db_path: Path,
    session_id: str,
    start_at: float,
    end_at: float,
    user_summary: str | None = None,
    system_summary: str | None = None,
    emotion_label: str | None = None,
    combined_summary: str | None = None,
    user_weight: float = 0.8,
    system_weight: float = 0.2,
    parent_session_id: str | None = None,
) -> None:
    """Insert an emotion segment row.

    Args:
        db_path: Path to SQLite database.
        session_id: Session identifier.
        start_at: Segment start timestamp (unix epoch).
        end_at: Segment end timestamp (unix epoch).
        user_summary: Summary of user messages in this window.
        system_summary: Summary of system actions (tools, traces) in this window.
        emotion_label: Computed emotion label (e.g. neutral, frustrated).
        combined_summary: Full combined summary for retrieval.
        user_weight: Weight for user signal (default 0.8).
        system_weight: Weight for system signal (default 0.2).
        parent_session_id: Parent session ID for child sessions; None for root.
    """
    if not db_path or not db_path.exists():
        return
    conn = _conn(db_path)
    try:
        conn.execute(
            """
            INSERT INTO emotion_segments (
                session_id, parent_session_id, start_at, end_at,
                user_weight, system_weight, user_summary, system_summary,
                emotion_label, combined_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                parent_session_id,
                start_at,
                end_at,
                user_weight,
                system_weight,
                user_summary,
                system_summary,
                emotion_label,
                combined_summary,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def query_by_session(
    db_path: Path,
    session_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get emotion segments for a session, newest first.

    Args:
        db_path: Path to SQLite database.
        session_id: Session identifier.
        limit: Max rows to return.

    Returns:
        List of segment dicts with keys: session_id, parent_session_id,
        start_at, end_at, user_summary, system_summary, emotion_label,
        combined_summary, created_at.
    """
    if not db_path or not db_path.exists():
        return []
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            """
            SELECT session_id, parent_session_id, start_at, end_at,
                   user_summary, system_summary, emotion_label, combined_summary,
                   created_at
            FROM emotion_segments WHERE session_id = ? OR parent_session_id = ?
            ORDER BY end_at DESC LIMIT ?
            """,
            (session_id, session_id, limit),
        )
        cols = [
            "session_id",
            "parent_session_id",
            "start_at",
            "end_at",
            "user_summary",
            "system_summary",
            "emotion_label",
            "combined_summary",
            "created_at",
        ]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def get_latest(db_path: Path | None = None) -> dict[str, Any] | None:
    """Get the most recent emotion segment (for orb ring).

    Returns:
        Dict with emotion_label, session_id or None if no segments.
    """
    if db_path is None:
        from config import get_config

        db_path = get_config().paths.db_path()
    segments = query_by_time(db_path, hours=None, limit=1)
    if not segments:
        return None
    s = segments[0]
    return {"emotion_label": s.get("emotion_label") or "neutral", "session_id": s.get("session_id")}


def query_recent_hours(
    db_path: Path,
    session_id: str,
    hours: float = 2.0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get emotion segments within the last N hours for a session.

    Args:
        db_path: Path to SQLite database.
        session_id: Session identifier (filters by session_id or parent_session_id).
        hours: Look back window in hours.
        limit: Max rows to return.

    Returns:
        List of segment dicts, newest first.
    """
    if not db_path or not db_path.exists():
        return []
    cutoff = time.time() - (hours * 3600)
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            """
            SELECT session_id, parent_session_id, start_at, end_at,
                   user_summary, system_summary, emotion_label, combined_summary,
                   created_at
            FROM emotion_segments
            WHERE (session_id = ? OR parent_session_id = ?) AND end_at >= ?
            ORDER BY end_at DESC LIMIT ?
            """,
            (session_id, session_id, cutoff, limit),
        )
        cols = [
            "session_id",
            "parent_session_id",
            "start_at",
            "end_at",
            "user_summary",
            "system_summary",
            "emotion_label",
            "combined_summary",
            "created_at",
        ]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def query_by_time(
    db_path: Path,
    hours: float | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get emotion segments across all sessions, ordered by time (newest first).

    No session filter. Default retrieval for emotion-awareness.

    Args:
        db_path: Path to SQLite database.
        hours: Optional look back window in hours. None = no time filter.
        limit: Max rows to return.

    Returns:
        List of segment dicts with keys: session_id, parent_session_id,
        start_at, end_at, user_summary, system_summary, emotion_label,
        combined_summary, created_at.
    """
    if not db_path or not db_path.exists():
        return []
    conn = _conn(db_path)
    try:
        if hours is not None:
            cutoff = time.time() - (hours * 3600)
            cur = conn.execute(
                """
                SELECT session_id, parent_session_id, start_at, end_at,
                       user_summary, system_summary, emotion_label, combined_summary,
                       created_at
                FROM emotion_segments
                WHERE end_at >= ?
                ORDER BY end_at DESC LIMIT ?
                """,
                (cutoff, limit),
            )
        else:
            cur = conn.execute(
                """
                SELECT session_id, parent_session_id, start_at, end_at,
                       user_summary, system_summary, emotion_label, combined_summary,
                       created_at
                FROM emotion_segments
                ORDER BY end_at DESC LIMIT ?
                """,
                (limit,),
            )
        cols = [
            "session_id",
            "parent_session_id",
            "start_at",
            "end_at",
            "user_summary",
            "system_summary",
            "emotion_label",
            "combined_summary",
            "created_at",
        ]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()

