"""Background enqueue and async runner for emotion segment analysis."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from config import get_config
from db import emotion as db_emotion
from db import session_meta
from _lib.analyzer import analyze_segment

logger = logging.getLogger(__name__)

_SEGMENT_WINDOW_SEC = 300.0


def enqueue_segment_analysis(
    db_path: Path,
    session_id: str,
    user_message: str,
    assistant_message: str,
    start_at: float | None = None,
) -> None:
    """Schedule async emotion analysis when enabled and the DB exists.

    Args:
        db_path (Path): Application SQLite path.
        session_id (str): Conversation session.
        user_message (str): User text in the segment.
        assistant_message (str): Assistant reply in the segment.
        start_at (float | None): Segment start epoch; default is a short lookback window.
    """
    cfg = get_config()
    if not cfg.emotion.enabled:
        return
    if not db_path or not db_path.exists():
        return
    end_at = time.time()
    if start_at is None:
        start_at = end_at - _SEGMENT_WINDOW_SEC
    asyncio.create_task(
        _run_segment_analysis(
            db_path=db_path,
            session_id=session_id,
            user_message=user_message,
            assistant_message=assistant_message,
            start_at=start_at,
            end_at=end_at,
        )
    )


async def _run_segment_analysis(
    db_path: Path,
    session_id: str,
    user_message: str,
    assistant_message: str,
    start_at: float,
    end_at: float,
) -> None:
    """Call ``analyze_segment``, persist to ``db.emotion``, optionally broadcast SSE.

    Args:
        db_path (Path): SQLite path.
        session_id (str): Session analyzed.
        user_message (str): User text anchor.
        assistant_message (str): Assistant text anchor.
        start_at (float): Segment start epoch.
        end_at (float): Segment end epoch.
    """
    try:
        user_summary, system_summary, emotion_label = await analyze_segment(
            db_path=db_path,
            session_id=session_id,
            user_message=user_message,
            assistant_message=assistant_message,
            start_at=start_at,
            end_at=end_at,
        )
        cfg = get_config()
        combined = _format_combined(user_summary, system_summary, cfg.emotion)
        parent_id = _get_parent_id(db_path, session_id)
        db_emotion.insert(
            db_path=db_path,
            session_id=session_id,
            start_at=start_at,
            end_at=end_at,
            user_summary=user_summary,
            system_summary=system_summary,
            emotion_label=emotion_label,
            combined_summary=combined,
            user_weight=cfg.emotion.user_weight,
            system_weight=cfg.emotion.system_weight,
            parent_session_id=parent_id,
        )
        logger.debug("[emotion] segment saved session_id=%s emotion=%s", session_id, emotion_label)
        try:
            from api.schemas.event_types import EMOTION_UPDATED
            from services.state import broadcast_event
            broadcast_event({"type": EMOTION_UPDATED, "emotion_label": emotion_label, "session_id": session_id})
        except Exception:
            pass
    except Exception as e:
        logger.warning("[emotion] segment analysis failed: %s", e, exc_info=True)


def _format_combined(
    user_summary: str | None,
    system_summary: str | None,
    emotion_cfg: Any,
) -> str:
    parts: list[str] = []
    if user_summary:
        parts.append(f"[User {emotion_cfg.user_weight:.0%}] {user_summary}")
    if system_summary:
        parts.append(f"[System {emotion_cfg.system_weight:.0%}] {system_summary}")
    return " | ".join(parts) if parts else ""


def _get_parent_id(db_path: Path, session_id: str) -> str | None:
    meta = session_meta.get(db_path, session_id)
    return meta.get("parent_id") if meta else None
