"""Session CRUD, message fetch, tree shaping, fork, and id resolution.

Resolves short or ambiguous ``session_id`` values against long-term memory and
``session_meta`` parent/child links before DB operations.
"""

import logging
from pathlib import Path

from fastapi import HTTPException
from common.utils import new_session_id, get_db_path
from db import memory_long_term, session_meta as db_session_meta
from db.schema import get_connection

logger = logging.getLogger(__name__)


def resolve_session(db_path: Path, session_id: str) -> str | None:
    """Resolve a short or ambiguous session id to the canonical stored id.

    Args:
        db_path (Path): SQLite path for the active user.
        session_id (str): Client-supplied id (may be suffix or parent key).

    Returns:
        Canonical ``session_id`` when found; otherwise ``None``.
    """
    resolved = memory_long_term.resolve_session_id(db_path, session_id)
    if resolved:
        return resolved

    if not db_path.exists():
        return None

    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT 1 FROM memory_long_term WHERE session_id = ? LIMIT 1",
            (session_id,),
        )
        if cur.fetchone():
            return session_id
    finally:
        conn.close()

    for pid in db_session_meta.get_parent_ids(db_path):
        if pid == session_id or (len(session_id) >= 6 and pid.endswith(session_id)):
            return pid

    return None


def list_sessions(include: str | None = None, tree: bool = False) -> dict:
    """List sessions from memory tables with optional tree shaping.

    Args:
        include (str | None): Comma-separated ids to ensure appear in the list
            (zero message_count when not yet in memory).
        tree (bool): When True, return ``roots`` with nested ``children`` from
            ``session_meta``; when False, return flat ``sessions``.

    Returns:
        Dict with either ``sessions`` or ``roots`` depending on ``tree``.
    """
    db_path = get_db_path()
    sessions = memory_long_term.list_sessions(db_path)

    if include:
        for sid in [s.strip() for s in include.split(",") if s.strip()]:
            if not any(se["id"] == sid for se in sessions):
                sessions.append({"id": sid, "message_count": 0, "updated_at": None})

    if not tree:
        return {"sessions": sessions}

    return _build_session_tree(db_path, sessions, include)


def create_session() -> dict:
    """Allocate a new ``web-``-prefixed session id.

    Returns:
        Dict with key ``session_id``.
    """
    return {"session_id": new_session_id()}


def get_session_messages(session_id: str) -> dict:
    """Load full message rows for a session.

    Args:
        session_id (str): Session to resolve and load.

    Returns:
        Dict with ``session_id``, ``messages``, and optional ``status`` from
        ``session_meta`` for async child sessions.

    Raises:
        HTTPException: 404 when the session cannot be resolved.
    """
    db_path = get_db_path()
    sid = resolve_session(db_path, session_id)

    if sid is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    msgs = memory_long_term.get_messages(db_path, sid)
    result: dict = {"session_id": sid, "messages": msgs}

    if db_path.exists():
        meta = db_session_meta.get(db_path, sid)
        if meta:
            result["status"] = meta["status"]

    return result


def get_session_children(session_id: str) -> dict:
    """Return async child sessions registered under a parent id.

    Args:
        session_id (str): Parent session id (resolved if ambiguous).

    Returns:
        Dict with ``session_id`` and ``children`` list.

    Raises:
        HTTPException: 404 when the session cannot be resolved.
    """
    db_path = get_db_path()
    sid = resolve_session(db_path, session_id)

    if sid is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    children = db_session_meta.get_children(db_path, sid)
    return {"session_id": sid, "children": children}


def delete_session(session_id: str) -> dict:
    """Delete a session, its children, and associated memory rows.

    Args:
        session_id (str): Session to resolve and remove.

    Returns:
        Dict with ``deleted`` set to the canonical id.

    Raises:
        HTTPException: 404 when the session cannot be resolved.
    """
    db_path = get_db_path()
    sid = resolve_session(db_path, session_id)

    if sid is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if db_path.exists():
        for child in db_session_meta.get_children(db_path, sid):
            memory_long_term.delete_by_session(db_path, child["session_id"] )
            db_session_meta.delete_session(db_path, child["session_id"] )

        memory_long_term.delete_by_session(db_path, sid)
        db_session_meta.delete_session(db_path, sid)

    return {"deleted": sid}


def fork_session(session_id: str) -> dict:
    """Copy long-term memory from an existing session into a new id.

    Args:
        session_id (str): Source session (resolved if ambiguous).

    Returns:
        Dict with new ``session_id``.

    Raises:
        HTTPException: 404 when the source session cannot be resolved.
    """
    db_path = get_db_path()
    sid = resolve_session(db_path, session_id)

    if sid is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    new_id = new_session_id()

    if db_path.exists():
        memory_long_term.copy_to_new_session(db_path, sid, new_id)

    return {"session_id": new_id}


def _build_session_tree(
    db_path: Path,
    sessions: list[dict],
    include: str | None,
) -> dict:
    """Attach ``children`` arrays to root sessions for tree APIs.

    Args:
        db_path (Path): SQLite path.
        sessions (list[dict]): Flat session rows from memory list API.
        include (str | None): Comma-separated ids to force as roots.

    Returns:
        Dict with key ``roots`` (list of session dicts with ``children``).
    """
    child_ids = db_session_meta.get_child_ids(db_path)
    roots = [s for s in sessions if s["id"] not in child_ids]

    out = []
    seen_ids: set[str] = set()

    for root in roots:
        children = db_session_meta.get_children(db_path, root["id"])
        seen_ids.add(root["id"] )
        for child in children:
            seen_ids.add(child["session_id"] )

        out.append({
            "id": root["id"],
            "message_count": root["message_count"],
            "updated_at": root["updated_at"],
            "children": children,
        })

    for parent_id in db_session_meta.get_parent_ids(db_path):
        if parent_id not in seen_ids:
            seen_ids.add(parent_id)
            children = db_session_meta.get_children(db_path, parent_id)
            for child in children:
                seen_ids.add(child["session_id"] )
            out.append({
                "id": parent_id,
                "message_count": 0,
                "updated_at": None,
                "children": children,
            })

    if include:
        for raw in [s.strip() for s in include.split(",") if s.strip()]:
            sid = resolve_session(db_path, raw) or raw
            if sid not in seen_ids:
                out.append({
                    "id": sid,
                    "message_count": 0,
                    "updated_at": None,
                    "children": db_session_meta.get_children(db_path, sid),
                })

    return {"roots": out}
