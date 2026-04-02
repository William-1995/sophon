"""SSE stream for ``GET /api/events`` (async task lifecycle + heartbeat)."""

import asyncio
import json

from fastapi.responses import StreamingResponse
from api.schemas.event_types import HEARTBEAT
from services.state import add_event_subscriber, remove_event_subscriber

_HEARTBEAT_INTERVAL = 25.0  # seconds
_HEARTBEAT_EVENT = {"type": HEARTBEAT.value}

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

async def events_stream_generator():
    """Poll the subscriber queue with timeout; emit heartbeats between messages.

    Yields:
        str: SSE ``data: ...\\n\\n`` lines (JSON object strings or heartbeat).
    """
    queue = add_event_subscriber()
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_INTERVAL)
            except asyncio.TimeoutError:
                yield _format_sse(json.dumps(_HEARTBEAT_EVENT, ensure_ascii=False))
                continue

            if event is None:
                # Shutdown signal
                break

            yield _format_sse(json.dumps(event, ensure_ascii=False))
    finally:
        remove_event_subscriber(queue)


def get_events_stream() -> StreamingResponse:
    """Build the FastAPI response wrapping ``events_stream_generator``.

    Returns:
        StreamingResponse: ``text/event-stream`` with standard SSE headers.
    """
    return StreamingResponse(
        events_stream_generator(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


def _format_sse(data: str) -> str:
    """Format one SSE ``data`` field.

    Args:
        data (str): Payload placed after ``data: `` (typically JSON text).

    Returns:
        str: One SSE event block ending with a blank line.
    """
    return f"data: {data}\n\n"
