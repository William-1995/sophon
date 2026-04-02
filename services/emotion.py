"""Optional bridge to the emotion-awareness skill's background analyzer.

When the skill is importable, forwards to ``_lib.task.enqueue_segment_analysis``.
Otherwise defines a no-op ``enqueue_segment_analysis`` with the same signature so
chat handlers can import unconditionally.
"""

import logging
from pathlib import Path

from core.runtime_paths import emotion_awareness_scripts_dir, prepend_sys_path_once

logger = logging.getLogger(__name__)
prepend_sys_path_once([emotion_awareness_scripts_dir()])

try:  # pragma: no cover - optional dependency
    from _lib.task import enqueue_segment_analysis as _enqueue_segment_analysis  # type: ignore[attr-defined]

    def enqueue_segment_analysis(
        db_path: Path,
        session_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """Schedule emotion analysis for the latest user/assistant exchange.

        Args:
            db_path (Path): Application SQLite path.
            session_id (str): Conversation session.
            user_message (str): Last user text (possibly after @file stripping).
            assistant_message (str): Model reply text.
        """
        _enqueue_segment_analysis(
            db_path=db_path,
            session_id=session_id,
            user_message=user_message,
            assistant_message=assistant_message,
        )

except Exception:  # pragma: no cover - emotion skill not installed

    def enqueue_segment_analysis(
        db_path: Path,
        session_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """No-op when the emotion skill is unavailable (logs at INFO once per call).

        Args:
            db_path (Path): Unused in fallback.
            session_id (str): Used only for log context.
            user_message (str): Unused in fallback.
            assistant_message (str): Unused in fallback.
        """
        logger.info(
            "Emotion awareness skill not configured; skipping segment analysis "
            "for session_id=%s",
            session_id,
        )


__all__ = ["enqueue_segment_analysis"]
