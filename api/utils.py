"""
API Utilities - Helper functions for the FastAPI application.

Common utilities for path resolution, session management, and message parsing.
"""

import logging
import uuid
from pathlib import Path
from typing import Any

from config import get_config, SESSION_ID_LENGTH
from constants import CONTEXT_ASSISTANT_BRIEF_MAX, CONTEXT_USER_BRIEF_MAX
from db.schema import get_connection
from db import memory_long_term, session_meta as db_session_meta

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path and session utilities
# ---------------------------------------------------------------------------

def get_db_path() -> Path:
    """Get the database path from configuration.

    Returns:
        Path to the SQLite database.
    """
    return get_config().paths.db_path()


def get_workspace_path() -> Path:
    """Get the workspace path from configuration.

    Returns:
        Path to the user workspace.
    """
    return get_config().paths.user_workspace()


def new_session_id() -> str:
    """Generate a new session identifier.

    Returns:
        New session ID prefixed with 'web-'.
    """
    return f"web-{uuid.uuid4().hex[:SESSION_ID_LENGTH]}"


def new_run_id() -> str:
    """Generate a new run identifier.

    Returns:
        New run ID as UUID string.
    """
    return str(uuid.uuid4())


def new_message_id() -> str:
    """Generate a new message identifier.

    Returns:
        New message ID prefixed with 'msg_'.
    """
    return f"msg_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Message parsing utilities
# ---------------------------------------------------------------------------

def parse_messages(messages: list[dict]) -> tuple[str, list[dict], str]:
    """Extract system_prompt, context, and last user question from messages.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.

    Returns:
        Tuple of (system_prompt, context_messages, question).
        - system_prompt: Combined system messages.
        - context_messages: User/assistant history before last user message.
        - question: Content of last user message.
    """
    system_parts: list[str] = []
    user_assistant: list[dict] = []

    for msg in messages or []:
        role = (msg.get("role") or "user").lower()
        content = (msg.get("content") or "").strip()

        if role == "system":
            if content:
                system_parts.append(content)
        elif role in ("user", "assistant"):
            user_assistant.append({"role": role, "content": content})

    system_prompt = "\n".join(system_parts).strip() if system_parts else ""

    if not user_assistant:
        return system_prompt, [], ""

    # Last user message = current question; rest = context
    last_idx = -1
    for i in range(len(user_assistant) - 1, -1, -1):
        if user_assistant[i]["role"] == "user":
            last_idx = i
            break

    if last_idx < 0:
        return system_prompt, user_assistant, ""

    question = user_assistant[last_idx]["content"]
    context = user_assistant[:last_idx]
    return system_prompt, context, question


# ---------------------------------------------------------------------------
# Session resolution utilities
# ---------------------------------------------------------------------------

def resolve_session(db_path: Path, session_id: str) -> str | None:
    """Resolve partial session_id to full id.

    Tries multiple resolution strategies:
    1. Direct lookup via memory_long_term.resolve_session_id
    2. Direct match in memory_long_term table
    3. Match via session_meta parent_ids

    Args:
        db_path: Path to database.
        session_id: Partial or full session identifier.

    Returns:
        Full session ID or None if not found.
    """
    # Try direct resolution first
    resolved = memory_long_term.resolve_session_id(db_path, session_id)
    if resolved:
        return resolved

    if not db_path.exists():
        return None

    # Try direct match in memory table
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

    # Try matching via session_meta parent_ids
    for pid in db_session_meta.get_parent_ids(db_path):
        if pid == session_id or (len(session_id) >= 6 and pid.endswith(session_id)):
            return pid

    return None


# ---------------------------------------------------------------------------
# Context building utilities
# ---------------------------------------------------------------------------

def _condense_message(role: str, content: str) -> str:
    """Condense a single message for cross-run context to save tokens."""
    s = (content or "").strip()
    max_len = CONTEXT_USER_BRIEF_MAX if role == "user" else CONTEXT_ASSISTANT_BRIEF_MAX
    if len(s) <= max_len:
        return s
    return s[: max_len - 3].rstrip() + "..."


def condense_context_for_llm(messages: list[dict]) -> list[dict]:
    """Condense cross-run history for token savings. User and assistant get brief form.

    Does not touch within-run ctx.messages (those stay full for ReAct continuity).
    """
    if not messages:
        return []
    return [
        {"role": m.get("role", "user"), "content": _condense_message(m.get("role", "user"), m.get("content", ""))}
        for m in messages
    ]


def build_context_from_db(
    session_id: str,
    db_path: Path,
    limit: int | None = None,
) -> list[dict]:
    """Build conversation context from database.

    Args:
        session_id: Session identifier.
        db_path: Path to database.
        limit: Optional limit for recent messages.

    Returns:
        List of message dicts with 'role' and 'content'.
    """
    if not session_id or not db_path.exists():
        return []

    if limit is None:
        limit = get_config().memory.history_recent_count

    raw = memory_long_term.get_recent(db_path, session_id, limit=limit)
    return condense_context_for_llm(raw)


def build_context_from_history(history: list[dict]) -> list[dict]:
    """Build conversation context from history (deprecated fallback).

    Args:
        history: List of history entries.

    Returns:
        List of normalized message dicts.
    """
    if not history:
        return []

    raw = [
        {"role": entry.get("role", "user"), "content": entry.get("content", "")}
        for entry in history[-10:]
    ]
    return condense_context_for_llm(raw)


def build_chat_context(
    session_id: str | None,
    history: list[dict] | None,
    db_path: Path,
) -> list[dict]:
    """Build context from DB (preferred) or history (fallback).

    Args:
        session_id: Optional session identifier.
        history: Optional history list (deprecated).
        db_path: Path to database.

    Returns:
        List of context messages.
    """
    # Prefer DB when session_id is available
    if session_id and db_path.exists():
        ctx = build_context_from_db(session_id, db_path)
        if ctx:
            return ctx

    # Fallback to history for backward compatibility
    if history:
        return build_context_from_history(history)

    return []


# ---------------------------------------------------------------------------
# File reference utilities
# ---------------------------------------------------------------------------

def extract_file_references(text: str) -> list[str]:
    """Extract @filename references from text.

    Args:
        text: Input text that may contain @filename references.

    Returns:
        List of extracted filenames (without @ prefix).
    """
    import re

    pattern = r"@([^\s]+)"
    return [match.group(1) for match in re.finditer(pattern, text)]


def add_file_references_to_recent(db_path: Path, text: str) -> None:
    """Extract and add file references to recent files.

    Args:
        db_path: Path to database.
        text: Input text to scan for references.
    """
    if not db_path.exists():
        return

    from db.recent_files import add as add_recent_file

    for filename in extract_file_references(text):
        add_recent_file(db_path, filename)
