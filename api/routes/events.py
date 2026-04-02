"""Server-Sent Events feed for async task lifecycle (``TASK_*``) and heartbeats."""

from fastapi import APIRouter
from services.events import get_events_stream

router = APIRouter(tags=["events"])


@router.get("/api/events")
async def get_events():
    """Open a long-lived SSE connection to receive async task broadcasts.

    Returns:
        ``StreamingResponse`` with periodic heartbeats and task events as JSON lines.
    """
    return get_events_stream()
