"""Session meta: parent/child and status for async task tree."""
import time
from pathlib import Path

from db.schema import get_connection


def upsert(
    db_path: Path,
    session_id: str,
    *,
    parent_id: str | None = None,
    title: str = "",
    agent: str = "main",
    kind: str = "chat",
    status: str = "queued",
) -> None:
    """Insert or replace session meta row."""
    if not db_path.exists():
        return
    now = time.time()
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO session_meta (session_id, parent_id, title, agent, kind, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                parent_id = excluded.parent_id,
                title = CASE WHEN excluded.title != '' THEN excluded.title ELSE session_meta.title END,
                agent = excluded.agent,
                kind = excluded.kind,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (session_id, parent_id or None, title or "", agent, kind, status, now, now),
        )
        conn.commit()
    finally:
        conn.close()


def update_status(db_path: Path, session_id: str, status: str) -> None:
    """Update status and updated_at for a session."""
    if not db_path.exists():
        return
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE session_meta SET status = ?, updated_at = ? WHERE session_id = ?",
            (status, time.time(), session_id),
        )
        conn.commit()
    finally:
        conn.close()


def get(db_path: Path, session_id: str) -> dict | None:
    """Get one session meta row. Returns None if not found."""
    if not db_path.exists():
        return None
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT session_id, parent_id, title, agent, kind, status, created_at, updated_at FROM session_meta WHERE session_id = ?",
            (session_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "session_id": row[0],
            "parent_id": row[1],
            "title": row[2],
            "agent": row[3],
            "kind": row[4],
            "status": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }
    finally:
        conn.close()


def get_child_ids(db_path: Path) -> set[str]:
    """Return set of session_ids that have a parent (are children). Used to filter roots."""
    if not db_path.exists():
        return set()
    conn = get_connection()
    try:
        cur = conn.execute("SELECT session_id FROM session_meta WHERE parent_id IS NOT NULL")
        return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def get_parent_ids(db_path: Path) -> set[str]:
    """Return set of session_ids that are parents (have at least one child). Ensures tree shows parent even with no messages."""
    if not db_path.exists():
        return set()
    conn = get_connection()
    try:
        cur = conn.execute("SELECT DISTINCT parent_id FROM session_meta WHERE parent_id IS NOT NULL")
        return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def delete_session(db_path: Path, session_id: str) -> None:
    """Delete session_meta row for this session."""
    if not db_path.exists():
        return
    conn = get_connection()
    try:
        conn.execute("DELETE FROM session_meta WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()


def get_children(db_path: Path, parent_id: str) -> list[dict]:
    """List child sessions of a parent. Returns [{session_id, parent_id, title, agent, kind, status, created_at, updated_at}, ...]."""
    if not db_path.exists():
        return []
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT session_id, parent_id, title, agent, kind, status, created_at, updated_at
            FROM session_meta WHERE parent_id = ?
            ORDER BY created_at DESC
            """,
            (parent_id,),
        )
        return [
            {
                "session_id": row[0],
                "parent_id": row[1],
                "title": row[2],
                "agent": row[3],
                "kind": row[4],
                "status": row[5],
                "created_at": row[6],
                "updated_at": row[7],
            }
            for row in cur.fetchall()
        ]
    finally:
        conn.close()
