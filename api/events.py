"""
Events API - Server-Sent Events (SSE) streaming for async task lifecycle.

Provides event streaming for task status updates (TASK_STARTED, TASK_FINISHED, TASK_ERROR).
Includes heartbeat to keep connections alive.
"""

import asyncio
import json

from fastapi.responses import StreamingResponse

from api.event_types import HEARTBEAT
from api.state import add_event_subscriber, remove_event_subscriber


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_HEARTBEAT_INTERVAL = 25.0  # seconds
_HEARTBEAT_EVENT = {"type": HEARTBEAT.value}

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def events_stream_generator():
    """Generate SSE stream for async task events.

    Events include:
    - TASK_STARTED: Task execution began
    - TASK_FINISHED: Task completed successfully
    - TASK_ERROR: Task failed with error
    - heartbeat: Keep-alive (every 25 seconds)

    Yields:
        SSE formatted event strings.
    """
    queue = add_event_subscriber()
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_INTERVAL)
            except asyncio.TimeoutError:
                yield _format_sse(_HEARTBEAT_EVENT)
                continue

            if event is None:
                # Shutdown signal
                break

            yield _format_sse(json.dumps(event, ensure_ascii=False))
    finally:
        remove_event_subscriber(queue)


def get_events_stream() -> StreamingResponse:
    """Return SSE streaming response for events endpoint.

    Returns:
        StreamingResponse with SSE media type.
    """
    return StreamingResponse(
        events_stream_generator(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _format_sse(data: str) -> str:
    """Format data as SSE event line.

    Args:
        data: JSON string to format.

    Returns:
        SSE formatted line.
    """
    return f"data: {data}\n\n"
