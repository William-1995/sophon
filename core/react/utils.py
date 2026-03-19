"""
ReAct Utilities - Shared helper functions for ReAct execution.

Common utilities for text processing, event emission, and data transformation.
"""

import json
import logging
import re
from typing import Any

from constants import (
    OBSERVATIONS_COMBINED_MAX,
    OBSERVATION_BRIEF_MAX,
    OBSERVATIONS_KEEP_FULL_TAIL,
)

logger = logging.getLogger(__name__)

# Characters of composite body injected into system prompt for tool guidance
_COMPOSITE_BODY_INJECT_MAX = 1500

# Max chars of observations to store in cancel checkpoint
_CHECKPOINT_OBS_PREVIEW_LEN = 2000

# Prefix when observations are truncated (keep tail for LLM context)
_TRUNCATE_PREFIX = "...[truncated]\n"

# Regex for <thinking>...</thinking> blocks (non-greedy)
_THINKING_PATTERN = re.compile(r"<thinking>(.*?)</thinking>", re.DOTALL | re.IGNORECASE)

# Tracking query params to strip for URL deduplication
_TRACKING_PARAMS = frozenset(
    ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "fbclid", "from")
)


def _obs_brief(obs: str, max_len: int = OBSERVATION_BRIEF_MAX) -> str:
    """One-line summary for old-round observation."""
    s = (obs or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3].rstrip() + "..."


def truncate_observations_for_llm(
    observations: list[str],
    max_chars: int = OBSERVATIONS_COMBINED_MAX,
    summarize_old: bool = True,
) -> str:
    """Build 'Results:\n' + observations. Keeps recent full; older get brief form.

    When summarize_old and we have more than OBSERVATIONS_KEEP_FULL_TAIL observations,
    older ones are shortened to OBSERVATION_BRIEF_MAX chars each to save tokens.

    Args:
        observations: List of observation strings from tool executions.
        max_chars: Maximum characters to include in result.
        summarize_old: When True, use brief form for old observations.
    """
    if not observations:
        return "Results:\n"
    keep_full = OBSERVATIONS_KEEP_FULL_TAIL if summarize_old else len(observations)
    if len(observations) <= keep_full:
        summarized = observations
    else:
        brief = [_obs_brief(o) for o in observations[:-keep_full]]
        summarized = brief + observations[-keep_full:]
    content = "Results:\n" + "\n".join(summarized)
    if len(content) <= max_chars:
        return content
    keep_len = max_chars - len(_TRUNCATE_PREFIX)
    return _TRUNCATE_PREFIX + content[-keep_len:]


def extract_and_emit_thinking(
    content: str,
    event_sink: Any,
) -> str:
    """Extract <thinking>...</thinking> blocks, emit THINKING events, return stripped content.

    Args:
        content: LLM response content that may contain thinking blocks.
        event_sink: Callback to emit thinking events to.

    Returns:
        Content with thinking blocks removed.
    """
    if not content or not event_sink:
        return content
    stripped_parts: list[str] = []
    last_end = 0
    for m in _THINKING_PATTERN.finditer(content):
        stripped_parts.append(content[last_end : m.start()])
        try:
            event_sink({"type": "THINKING", "content": m.group(1).strip()})
        except Exception:
            pass
        last_end = m.end()
    stripped_parts.append(content[last_end:])
    return "".join(stripped_parts).strip()


def save_cancel_checkpoint(
    db: Any,
    session_id: str,
    run_id: str | None,
    round_num: int,
    question: str,
    observations: list[str],
    total_tokens: int,
    messages: list[dict[str, Any]] | None = None,
) -> None:
    """Persist run state before returning on cancel. Enables future resume or audit.

    Args:
        db: Database path for checkpoint storage.
        session_id: Session identifier.
        run_id: Run identifier (optional).
        round_num: Current round number.
        question: Current question being processed.
        observations: List of accumulated observations.
        total_tokens: Cumulative token count.
        messages: Current conversation messages (optional).
    """
    try:
        from db.logs import insert as log_insert
        obs_preview = "\n".join(observations)[:_CHECKPOINT_OBS_PREVIEW_LEN]
        if len(observations) and len(obs_preview) < sum(len(o) for o in observations):
            obs_preview += "..."
        log_insert(
            db,
            "INFO",
            "run_cancelled_checkpoint",
            session_id=session_id,
            metadata={
                "run_id": run_id,
                "round": round_num,
                "question_preview": (question or "")[:500],
                "observations_preview": obs_preview,
                "total_tokens": total_tokens,
            },
        )
        if run_id and messages is not None:
            from db import checkpoints
            checkpoints.insert(
                db, run_id, session_id, round_num, question,
                observations, messages, total_tokens,
            )
    except Exception as e:
        logger.debug("[react] checkpoint save failed: %s", e)


def extract_direct_answer(content: str) -> str:
    """Extract answer from JSON {\"answer\": \"...\"} if present; else return content.

    Args:
        content: Text that may contain a JSON-encoded answer.

    Returns:
        Extracted answer string or original content.
    """
    text = (content or "").strip()
    if text.startswith("{") and '"answer"' in text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed.get("answer"), str):
                return parsed["answer"].strip()
        except json.JSONDecodeError:
            pass
    return text


def format_skill_observation(result: dict) -> str:
    """Format skill result into observation string.

    Args:
        result: Skill execution result dictionary.

    Returns:
        Formatted observation string.
    """
    if result.get("error"):
        return f"Error: {result['error']}"
    content = result.get("content", "")
    if content:
        return content[:OBSERVATIONS_COMBINED_MAX]
    return json.dumps(result, ensure_ascii=False)[:OBSERVATIONS_COMBINED_MAX]


def normalize_url(url: str) -> str:
    """Normalize URL: lowercase, strip tracking query params.

    Args:
        url: URL string to normalize.

    Returns:
        Normalized URL or original string on failure.
    """
    from urllib.parse import parse_qs, urlparse, urlencode, urlunparse

    s = (url or "").strip().lower()
    if not s or not s.startswith(("http://", "https://")):
        return s
    try:
        p = urlparse(s)
        path = p.path.rstrip("/") or "/"
        qs = parse_qs(p.query, keep_blank_values=False)
        qs = {k: v for k, v in qs.items() if k.lower() not in _TRACKING_PARAMS}
        query = urlencode(sorted(qs.items())) if qs else ""
        return urlunparse((p.scheme, p.netloc.lower(), path, "", query, ""))
    except Exception:
        return s


def dedupe_references(refs: list[dict]) -> list[dict]:
    """Deduplicate references by normalized URL (strip tracking params).

    Args:
        refs: List of reference dicts with 'url' keys.

    Returns:
        Deduplicated list of references.
    """
    seen: set[str] = set()
    out: list[dict] = []
    for r in refs:
        url = (r.get("url") or "").strip()
        if not url:
            continue
        norm = normalize_url(url)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(r)
    return out


def emit_progress(
    callback: Any,
    total_tokens: int,
    round_num: int | None,
) -> None:
    """Emit progress update via callback if provided.

    Args:
        callback: Optional progress callback function.
        total_tokens: Current total token count.
        round_num: Current round number (None if finished).
    """
    if callback:
        try:
            callback(total_tokens, round_num)
        except Exception:
            pass
