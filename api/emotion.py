"""
Emotion awareness hook - optional.

If the emotion-awareness skill is installed, we import its task helper.
Otherwise, we expose a no-op enqueue_segment_analysis so the API can run
without the optional dependency.
"""

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_scripts_dir = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "optional"
    / "entertainment"
    / "emotion-awareness"
    / "scripts"
)
if _scripts_dir.exists() and str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

try:  # pragma: no cover - optional dependency
    from _lib.task import enqueue_segment_analysis as _enqueue_segment_analysis  # type: ignore[attr-defined]

    def enqueue_segment_analysis(
        db_path: Path,
        session_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """Forward to emotion-awareness task helper when available."""
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
        """Fallback when emotion skill is not installed: do nothing."""
        logger.info(
            "Emotion awareness skill not configured; skipping segment analysis "
            "for session_id=%s",
            session_id,
        )


__all__ = ["enqueue_segment_analysis"]

