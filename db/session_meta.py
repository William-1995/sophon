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


def get_root_session_id(db_path: Path, session_id: str) -> str:
    """Walk up parent_id until root (parent_id IS NULL). Returns session_id if already root or not in meta."""
    if not db_path.exists():
        return session_id
    seen: set[str] = set()
    current = session_id
    while current:
        if current in seen:
            return session_id  # cycle guard
        seen.add(current)
        meta = get(db_path, current)
        if not meta:
            return session_id
        pid = meta.get("parent_id")
        if not pid:
            return current
        current = pid
    return session_id


def get_session_ids_in_tree(db_path: Path, root_session_id: str) -> list[str]:
    """Return [root_session_id] + all descendant session_ids (BFS). Used for memory scope isolation."""
    if not db_path.exists():
        return [root_session_id]
    result: list[str] = [root_session_id]
    queue: list[str] = [root_session_id]
    while queue:
        pid = queue.pop(0)
        for child in get_children(db_path, pid):
            cid = child.get("session_id")
            if cid and cid not in result:
                result.append(cid)
                queue.append(cid)
    return result


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
