"""Session CRUD, message history, child sessions, and fork."""

from fastapi import APIRouter

from services.sessions import (
    create_session,
    delete_session,
    fork_session,
    get_session_children,
    get_session_messages,
    list_sessions,
)

router = APIRouter(tags=["sessions"])


@router.post("/api/sessions")
def post_create_session() -> dict:
    """Create a new empty session id (messages stored on first chat).

    Returns:
        Dict with ``session_id``.
    """
    return create_session()


@router.get("/api/sessions")
def get_list_sessions(include: str | None = None, tree: bool = False) -> dict:
    """List sessions, optionally as a parent/child tree.

    Args:
        include (str | None): Comma-separated session ids to force-include.
        tree (bool): When True, return ``roots`` with nested children.

    Returns:
        ``sessions`` list or tree-shaped dict per service layer.
    """
    return list_sessions(include, tree)


@router.get("/api/sessions/{session_id}/messages")
def get_messages(session_id: str) -> dict:
    """Return full message history for a session (supports partial id match).

    Args:
        session_id (str): Session or suffix resolvable in the database.

    Returns:
        ``session_id``, ``messages``, and optional async ``status``.
    """
    return get_session_messages(session_id)


@router.get("/api/sessions/{session_id}/children")
def get_children(session_id: str) -> dict:
    """List child sessions (e.g. background tasks) for a parent session.

    Args:
        session_id (str): Parent session id.

    Returns:
        ``session_id`` and ``children`` metadata list.
    """
    return get_session_children(session_id)


@router.delete("/api/sessions/{session_id}")
def delete_session_endpoint(session_id: str) -> dict:
    """Delete a session, its memory rows, and dependent children.

    Args:
        session_id (str): Session to delete.

    Returns:
        Dict with ``deleted`` full session id.
    """
    return delete_session(session_id)


@router.post("/api/sessions/{session_id}/fork")
def fork_session_endpoint(session_id: str) -> dict:
    """Copy conversation history into a new session id.

    Args:
        session_id (str): Source session.

    Returns:
        Dict with new ``session_id``.
    """
    return fork_session(session_id)
