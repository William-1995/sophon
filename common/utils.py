"""Shared helpers for API routes: paths, ids, and message parsing."""

import logging
import re
import uuid
from pathlib import Path

from config import get_config, SESSION_ID_LENGTH
from constants import (
    API_MESSAGE_ID_RANDOM_HEX_SUFFIX_LEN,
    CONTEXT_ASSISTANT_BRIEF_MAX,
    CONTEXT_USER_BRIEF_MAX,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path and ID helpers
# ---------------------------------------------------------------------------

def get_db_path() -> Path:
    """Return the configured SQLite path for the default user."""
    return get_config().paths.db_path()


def get_workspace_path() -> Path:
    """Return the default user's workspace root directory."""
    return get_config().paths.user_workspace()


def new_session_id() -> str:
    """Allocate a new browser/API session id."""
    return f"web-{uuid.uuid4().hex[:SESSION_ID_LENGTH]}"


def new_run_id() -> str:
    """Allocate a UUID4 string for correlating streams and cancellations."""
    return str(uuid.uuid4())


def new_message_id() -> str:
    """Create an AG-UI style assistant message id."""
    return f"msg_{uuid.uuid4().hex[:API_MESSAGE_ID_RANDOM_HEX_SUFFIX_LEN]}"


# ---------------------------------------------------------------------------
# Message parsing utilities
# ---------------------------------------------------------------------------

def parse_messages(messages: list[dict]) -> tuple[str, list[dict], str]:
    """Split OpenAI-style ``messages`` into system text, prior turns, and latest user text."""
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
# Context helpers
# ---------------------------------------------------------------------------

def _condense_message(role: str, content: str) -> str:
    """Truncate one message to configured per-role limits for cross-run context."""
    s = (content or "").strip()
    max_len = CONTEXT_USER_BRIEF_MAX if role == "user" else CONTEXT_ASSISTANT_BRIEF_MAX
    if len(s) <= max_len:
        return s
    return s[: max_len - 3].rstrip() + "..."


def condense_context_for_llm(messages: list[dict]) -> list[dict]:
    """Map messages through ``_condense_message`` for cheaper prompt injection."""
    if not messages:
        return []
    return [
        {"role": m.get("role", "user"), "content": _condense_message(m.get("role", "user"), m.get("content", ""))}
        for m in messages
    ]


def build_context_from_history(history: list[dict]) -> list[dict]:
    """Normalize legacy ``history`` request field into condensed messages."""
    if not history:
        return []

    raw = [
        {"role": entry.get("role", "user"), "content": entry.get("content", "")}
        for entry in history[-10:]
    ]
    return condense_context_for_llm(raw)


# ---------------------------------------------------------------------------
# File reference utilities
# ---------------------------------------------------------------------------

def extract_file_references(text: str) -> list[str]:
    """Find ``@token`` references in user text (whitespace-delimited)."""
    pattern = r"@([^\s]+)"
    return [match.group(1) for match in re.finditer(pattern, text)]
