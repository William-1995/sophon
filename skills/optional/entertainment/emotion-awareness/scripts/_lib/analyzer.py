"""LLM sub-agent that infers user emotion from a conversation segment.

Builds an independent context from memory and traces; not the main agent's scratchpad.
"""

import json
import logging
from pathlib import Path

from config import get_config
from constants import (
    EMOTION_ANALYZER_FALLBACK_SUMMARY_MAX_CHARS,
    EMOTION_ANALYZER_MESSAGES_IN_RANGE_LIMIT,
    EMOTION_ANALYZER_SEGMENT_MAX_CHARS,
    EMOTION_ANALYZER_TRACE_LINES_IN_SEGMENT_MAX,
    EMOTION_ANALYZER_TRACE_PREVIEW_LEN,
)
from db import memory_long_term
from db import traces
from providers import get_provider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an emotion perception sub-agent. Your task is to perceive the user's emotional state based on the conversation segment provided.

You will receive:
1. The user's actual questions and messages (user questions)
2. Assistant replies
3. Optional system/tool activity summaries

Perceive the user's emotion from tone, wording, and reaction. Consider sarcasm, frustration, satisfaction, disappointment, amusement, etc.

Respond with a JSON object only, no other text:
{"emotion_label": "<string>", "user_summary": "<brief>", "system_summary": "<brief>"}

emotion_label: one of frustrated, satisfied, neutral, disappointed, amused, confused, anxious, relieved, or similar.
user_summary: 1-2 sentences summarizing the user's messages and tone.
system_summary: 1-2 sentences summarizing what the assistant/system did (tools, outcomes) if any.
"""

async def analyze_segment(
    db_path: Path,
    session_id: str,
    user_message: str,
    assistant_message: str,
    start_at: float,
    end_at: float,
) -> tuple[str | None, str | None, str | None]:
    """Run the perception LLM on messages and trace lines in ``[start_at, end_at]``.

    Args:
        db_path (Path): SQLite path.
        session_id (str): Session to analyze.
        user_message (str): Latest user text (anchor for the segment).
        assistant_message (str): Latest assistant text.
        start_at (float): Segment window start (epoch).
        end_at (float): Segment window end (epoch).

    Returns:
        tuple[str | None, str | None, str | None]: ``(emotion_label, user_summary, system_summary)``.
    """
    segment_text = _build_segment_for_perception(
        db_path=db_path,
        session_id=session_id,
        user_message=user_message,
        assistant_message=assistant_message,
        start_at=start_at,
        end_at=end_at,
    )
    if not segment_text or not segment_text.strip():
        return None, None, "neutral"

    cfg = get_config()
    model = cfg.emotion.model or cfg.llm.default_model
    provider = get_provider(model=model)

    messages = [{"role": "user", "content": segment_text}]
    try:
        resp = await provider.chat(
            messages=messages,
            system_prompt=_SYSTEM_PROMPT,
        )
        content = (resp.get("content") or "").strip()
        parsed = _parse_emotion_response(content)
        if parsed:
            return parsed.get("user_summary"), parsed.get("system_summary"), parsed.get("emotion_label", "neutral")
    except Exception as e:
        logger.warning("[emotion] sub-agent chat failed: %s", e, exc_info=True)

    combined = f"User: {user_message}\nAssistant: {assistant_message}" if user_message or assistant_message else ""
    user_sum = combined[:EMOTION_ANALYZER_FALLBACK_SUMMARY_MAX_CHARS] if combined else None
    return user_sum, None, "neutral"


def _build_segment_for_perception(
    db_path: Path,
    session_id: str,
    user_message: str,
    assistant_message: str,
    start_at: float,
    end_at: float,
) -> str:
    """Build conversation segment with user's actual questions for perception."""
    msgs = memory_long_term.get_in_time_range(
        db_path, session_id, start_at, end_at, limit=EMOTION_ANALYZER_MESSAGES_IN_RANGE_LIMIT
    )
    parts: list[str] = []

    if msgs:
        for m in msgs:
            role = m.get("role", "user")
            content = (m.get("content") or "").strip()
            if not content:
                continue
            label = "User" if role == "user" else "Assistant"
            parts.append(f"[{label}]\n{content}")
    else:
        if user_message:
            parts.append(f"[User]\n{user_message}")
        if assistant_message:
            parts.append(f"[Assistant]\n{assistant_message}")

    if not parts:
        return ""

    tracelist = traces.query_range(db_path, session_id, start_at, end_at)
    if tracelist:
        trace_lines = []
        for t in tracelist:
            skill = t.get("skill") or "?"
            action = t.get("action") or "?"
            preview = (t.get("result_preview") or "")[:EMOTION_ANALYZER_TRACE_PREVIEW_LEN]
            trace_lines.append(f"  - {skill}.{action}: {preview}" if preview else f"  - {skill}.{action}")
        parts.append(
            "[System activity]\n"
            + "\n".join(trace_lines[:EMOTION_ANALYZER_TRACE_LINES_IN_SEGMENT_MAX])
        )

    combined = "\n\n".join(parts)
    if len(combined) > EMOTION_ANALYZER_SEGMENT_MAX_CHARS:
        return combined[:EMOTION_ANALYZER_SEGMENT_MAX_CHARS]
    return combined


def _parse_emotion_response(content: str) -> dict | None:
    """Parse JSON from LLM response. Handles markdown code blocks."""
    content = content.strip()
    if "```" in content:
        start = content.find("```")
        if start >= 0:
            rest = content[start + 3:]
            if rest.lstrip().startswith("json"):
                rest = rest.lstrip()[4:]
            end = rest.find("```")
            content = rest[:end] if end >= 0 else rest
    try:
        obj = json.loads(content)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None
