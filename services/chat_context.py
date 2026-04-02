"""Build LLM chat context from DB history or inline ``history``."""

from pathlib import Path

from common.utils import build_context_from_history, condense_context_for_llm
from config import get_config
from db import memory_long_term


def build_uploaded_files_context(uploaded_files: list[str] | None) -> list[dict]:
    """Create a system note that makes uploaded files visible to the model.

    This keeps the rule explicit: uploaded file names are part of the current
    conversation context and should be preferred when the user refers to
    "this file", "these files", or similar deictic language.
    """
    normalized = [str(path).strip() for path in (uploaded_files or []) if str(path).strip()]
    if not normalized:
        return []

    lines = [
        "The user uploaded these files for the current turn:",
        *[f"- {path}" for path in normalized],
        "Treat these as the default file context for the request.",
        "When the user says 'this file', 'these files', 'attached files', or refers to a filename,",
        "prefer matching against this uploaded file list before guessing other workspace files.",
    ]
    return [{"role": "system", "content": "\n".join(lines)}]


def build_context_from_db(
    session_id: str,
    db_path: Path,
    limit: int | None = None,
) -> list[dict]:
    """Load recent memory rows for a session and condense them for the LLM.

    Args:
        session_id (str): Session key.
        db_path (Path): SQLite path; empty list when missing or no session.
        limit (int | None): Max recent rows; default from ``MemoryConfig.history_recent_count``.

    Returns:
        Condensed message dicts suitable for the provider context.
    """
    if not session_id or not db_path.exists():
        return []

    if limit is None:
        limit = get_config().memory.history_recent_count

    raw = memory_long_term.get_recent(db_path, session_id, limit=limit)
    return condense_context_for_llm(raw)


def build_chat_context(
    session_id: str | None,
    history: list[dict] | None,
    db_path: Path,
    uploaded_files: list[str] | None = None,
) -> list[dict]:
    """Prefer DB-backed history when ``session_id`` resolves; else use ``history``.

    Args:
        session_id (str | None): When set and DB has rows, load from DB first.
        history (list[dict] | None): Fallback inline turns from the client.
        db_path (Path): SQLite path for DB-backed branch.

    Returns:
        Context list (possibly empty).
    """
    uploaded_ctx = build_uploaded_files_context(uploaded_files)

    if session_id and db_path.exists():
        ctx = build_context_from_db(session_id, db_path)
        if ctx:
            return uploaded_ctx + ctx

    if history:
        return uploaded_ctx + build_context_from_history(history)

    return uploaded_ctx
