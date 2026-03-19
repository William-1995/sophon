"""Memory long-term - store conversation history."""
import json
import time
from pathlib import Path
from typing import Any

from db.schema import get_connection


def resolve_session_id(db_path: Path, q: str) -> str | None:
    """
    Resolve partial session_id to full session_id. Returns exact match or unique suffix match.
    e.g. 'dba17e07' -> 'web-dba17e07' if unique. Returns None if no match or ambiguous.
    """
    if not q or not db_path.exists():
        return None
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT session_id FROM memory_long_term WHERE session_id = ? OR session_id LIKE ? GROUP BY session_id",
            (q.strip(), f"%{q.strip()}"),
        )
        rows = cur.fetchall()
        if len(rows) == 1:
            return rows[0][0]
        return None
    finally:
        conn.close()


def insert(
    db_path: Path,
    session_id: str,
    role: str,
    content: str,
    references: list[dict[str, Any]] | None = None,
) -> None:
    """Insert conversation message. references: optional [{title, url}] for assistant role."""
    refs_json = json.dumps(references, ensure_ascii=False) if references else None
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO memory_long_term (session_id, role, content, refs_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, refs_json, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def get_in_time_range(
    db_path: Path,
    session_id: str,
    start_at: float,
    end_at: float,
    limit: int = 50,
) -> list[dict]:
    """Get messages in a time range for a session, oldest first.

    Args:
        db_path: Path to SQLite database (used for existence check).
        session_id: Session identifier.
        start_at: Start timestamp (inclusive).
        end_at: End timestamp (inclusive).
        limit: Max rows to return.

    Returns:
        List of dicts with role, content, created_at.
    """
    if not db_path.exists():
        return []
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT role, content, created_at
            FROM memory_long_term
            WHERE session_id = ? AND created_at >= ? AND created_at <= ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (session_id, start_at, end_at, limit),
        )
        return [
            {"role": row[0], "content": row[1], "created_at": row[2]}
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


def get_recent(db_path: Path, session_id: str, limit: int = 20) -> list[dict]:
    """Get recent messages for context injection. Returns [{role, content}, ...] in chronological order (oldest of the recent set first)."""
    if not db_path.exists():
        return []
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT role, content FROM memory_long_term WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (session_id, limit),
        )
        rows = cur.fetchall()
        return [{"role": row[0], "content": row[1]} for row in reversed(rows)]
    finally:
        conn.close()


def get_messages(db_path: Path, session_id: str, limit: int = 200) -> list[dict]:
    """Get full message list for a session (for display/fork). Returns [{role, content, references?, created_at?}, ...]."""
    if not db_path.exists():
        return []
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT role, content, refs_json, created_at FROM memory_long_term WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
            (session_id, limit),
        )
        rows = cur.fetchall()
        out: list[dict] = []
        for row in rows:
            msg: dict = {"role": row[0], "content": row[1]}
            if len(row) > 2 and row[2]:
                try:
                    msg["references"] = json.loads(row[2])
                except (json.JSONDecodeError, TypeError):
                    pass
            if len(row) > 3 and row[3] is not None:
                msg["created_at"] = row[3]
            out.append(msg)
        return out
    finally:
        conn.close()


def delete_by_session(db_path: Path, session_id: str) -> int:
    """Delete all messages for a session. Returns deleted count."""
    if not db_path.exists():
        return 0
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM memory_long_term WHERE session_id = ?", (session_id,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def copy_to_new_session(db_path: Path, old_session_id: str, new_session_id: str) -> int:
    """Copy all messages from old session to new. Returns copied count."""
    if not db_path.exists():
        return 0
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO memory_long_term (session_id, role, content, refs_json, created_at) "
            "SELECT ?, role, content, refs_json, created_at FROM memory_long_term WHERE session_id = ?",
            (new_session_id, old_session_id),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def list_sessions(db_path: Path, limit: int = 50) -> list[dict]:
    """List sessions with message count and last updated. Returns [{id, message_count, updated_at}, ...]."""
    if not db_path.exists():
        return []
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT session_id, COUNT(*) as cnt, MAX(created_at) as updated
            FROM memory_long_term GROUP BY session_id
            ORDER BY updated DESC LIMIT ?
            """,
            (limit,),
        )
        return [
            {"id": row[0], "message_count": row[1], "updated_at": row[2]}
            for row in cur.fetchall()
        ]
    finally:
        conn.close()
