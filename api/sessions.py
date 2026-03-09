"""
Session Management - Session CRUD and parent/child relationship handling.

All session-related endpoints including:
- List, create, delete sessions
- Get session messages
- Get session children
- Fork sessions
"""

import logging
from pathlib import Path

from fastapi import HTTPException
from api.utils import new_session_id, resolve_session, get_db_path
from db import memory_long_term, session_meta as db_session_meta

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_sessions(include: str | None = None, tree: bool = False) -> dict:
    """List sessions with optional filtering and tree view.

    Args:
        include: Optional comma-separated session IDs to include even if empty.
        tree: If True, return parent/child tree structure.

    Returns:
        Session list or tree response dict.
    """
    db_path = get_db_path()
    sessions = memory_long_term.list_sessions(db_path)

    # Include additional sessions if requested
    if include:
        for sid in [s.strip() for s in include.split(",") if s.strip()]:
            if not any(se["id"] == sid for se in sessions):
                sessions.append({"id": sid, "message_count": 0, "updated_at": None})

    if not tree:
        return {"sessions": sessions}

    # Build tree structure
    return _build_session_tree(db_path, sessions, include)


def create_session() -> dict:
    """Create a new session.

    Returns:
        Session creation response with new session_id.
    """
    return {"session_id": new_session_id()}


def get_session_messages(session_id: str) -> dict:
    """Get messages for a session.

    Supports partial session_id resolution.
    Includes status when session has session_meta (async task).

    Args:
        session_id: Session identifier (can be partial).

    Returns:
        Session messages response.

    Raises:
        HTTPException: If session not found.
    """
    db_path = get_db_path()
    sid = resolve_session(db_path, session_id)

    if sid is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    msgs = memory_long_term.get_messages(db_path, sid)
    result: dict = {"session_id": sid, "messages": msgs}

    # Include status for async tasks
    if db_path.exists():
        meta = db_session_meta.get(db_path, sid)
        if meta:
            result["status"] = meta["status"]

    return result


def get_session_children(session_id: str) -> dict:
    """List child sessions (async task tree).

    Args:
        session_id: Parent session identifier.

    Returns:
        Session children response with metadata.

    Raises:
        HTTPException: If session not found.
    """
    db_path = get_db_path()
    sid = resolve_session(db_path, session_id)

    if sid is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    children = db_session_meta.get_children(db_path, sid)
    return {"session_id": sid, "children": children}


def delete_session(session_id: str) -> dict:
    """Delete session and its memory.

    Cascade deletes all children.
    Supports partial session_id resolution.

    Args:
        session_id: Session identifier to delete.

    Returns:
        Deletion confirmation.

    Raises:
        HTTPException: If session not found.
    """
    db_path = get_db_path()
    sid = resolve_session(db_path, session_id)

    if sid is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if db_path.exists():
        # Delete all children first
        for child in db_session_meta.get_children(db_path, sid):
            memory_long_term.delete_by_session(db_path, child["session_id"])
            db_session_meta.delete_session(db_path, child["session_id"])

        # Delete parent
        memory_long_term.delete_by_session(db_path, sid)
        db_session_meta.delete_session(db_path, sid)

    return {"deleted": sid}


def fork_session(session_id: str) -> dict:
    """Fork session: copy history to new session.

    Supports partial session_id resolution.

    Args:
        session_id: Session identifier to fork.

    Returns:
        Fork response with new session_id.

    Raises:
        HTTPException: If session not found.
    """
    db_path = get_db_path()
    sid = resolve_session(db_path, session_id)

    if sid is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    new_id = new_session_id()

    if db_path.exists():
        memory_long_term.copy_to_new_session(db_path, sid, new_id)

    return {"session_id": new_id}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_session_tree(
    db_path: Path,
    sessions: list[dict],
    include: str | None,
) -> dict:
    """Build parent/child tree structure from sessions.

    Args:
        db_path: Path to database.
        sessions: List of session dicts.
        include: Optional include filter.

    Returns:
        Tree response with roots and children.
    """
    child_ids = db_session_meta.get_child_ids(db_path)
    roots = [s for s in sessions if s["id"] not in child_ids]

    out = []
    seen_ids: set[str] = set()

    for root in roots:
        children = db_session_meta.get_children(db_path, root["id"])
        seen_ids.add(root["id"])
        for child in children:
            seen_ids.add(child["session_id"])

        out.append({
            "id": root["id"],
            "message_count": root["message_count"],
            "updated_at": root["updated_at"],
            "children": children,
        })

    # Include parents that have children but may have no messages
    for parent_id in db_session_meta.get_parent_ids(db_path):
        if parent_id not in seen_ids:
            seen_ids.add(parent_id)
            children = db_session_meta.get_children(db_path, parent_id)
            for child in children:
                seen_ids.add(child["session_id"])
            out.append({
                "id": parent_id,
                "message_count": 0,
                "updated_at": None,
                "children": children,
            })

    # Add any explicitly included sessions not yet seen
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
