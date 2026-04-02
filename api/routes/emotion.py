"""Latest emotion summary for the orb UI (backed by ``db.emotion``)."""

from fastapi import APIRouter
from db.emotion import get_latest as get_latest_emotion

router = APIRouter(tags=["emotion"])


@router.get("/api/emotion/latest")
def get_emotion_latest() -> dict:
    """Return the most recent emotion analysis row, or null fields if none.

    Returns:
        Dict with ``emotion_label`` and ``session_id`` (or nulls).
    """
    latest = get_latest_emotion()
    return latest if latest else {"emotion_label": None, "session_id": None}
