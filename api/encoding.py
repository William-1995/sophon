"""
AG-UI Encoding - Event encoding for AG-UI protocol.

Encodes internal event dicts to AG-UI formatted SSE events.
Falls back to JSON encoding if ag-ui library is not available.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def encode_ag_ui_event(event: dict[str, Any]) -> str:
    """Encode AG-UI event to SSE line.

    Uses ag-ui-protocol when available, otherwise falls back to JSON.
    Handles all standard AG-UI event types:
    - RUN_STARTED
    - RUN_FINISHED
    - RUN_ERROR
    - RUN_CANCELLED
    - TEXT_MESSAGE_START
    - TEXT_MESSAGE_CONTENT
    - TEXT_MESSAGE_END
    - CUSTOM

    Args:
        event: Event dict with 'type' and type-specific fields.

    Returns:
        SSE formatted event string.
    """
    try:
        # Try to use ag-ui library for proper encoding
        from ag_ui.core import EventType
        from ag_ui.encoder import EventEncoder

        encoder = EventEncoder()
        event_type = event.get("type")

        if event_type == "RUN_STARTED":
            from ag_ui.core import RunStartedEvent
            ev = RunStartedEvent(
                type=EventType.RUN_STARTED,
                thread_id=event["threadId"],
                run_id=event["runId"],
            )
            return encoder.encode(ev)

        elif event_type == "RUN_FINISHED":
            from ag_ui.core import RunFinishedEvent
            ev = RunFinishedEvent(
                type=EventType.RUN_FINISHED,
                thread_id=event["threadId"],
                run_id=event["runId"],
                result=event.get("result"),
            )
            return encoder.encode(ev)

        elif event_type == "RUN_ERROR":
            from ag_ui.core import RunErrorEvent
            ev = RunErrorEvent(
                type=EventType.RUN_ERROR,
                message=event["message"],
            )
            return encoder.encode(ev)

        elif event_type == "RUN_CANCELLED":
            # RUN_CANCELLED not in base ag-ui, use JSON fallback
            return _encode_json_event(event)

        elif event_type == "TEXT_MESSAGE_START":
            from ag_ui.core import TextMessageStartEvent
            ev = TextMessageStartEvent(
                type=EventType.TEXT_MESSAGE_START,
                message_id=event["messageId"],
                role="assistant",
            )
            return encoder.encode(ev)

        elif event_type == "TEXT_MESSAGE_CONTENT":
            from ag_ui.core import TextMessageContentEvent
            ev = TextMessageContentEvent(
                type=EventType.TEXT_MESSAGE_CONTENT,
                message_id=event["messageId"],
                delta=event["delta"],
            )
            return encoder.encode(ev)

        elif event_type == "TEXT_MESSAGE_END":
            from ag_ui.core import TextMessageEndEvent
            ev = TextMessageEndEvent(
                type=EventType.TEXT_MESSAGE_END,
                message_id=event["messageId"],
            )
            return encoder.encode(ev)

        elif event_type == "CUSTOM":
            from ag_ui.core import CustomEvent
            ev = CustomEvent(
                type=EventType.CUSTOM,
                name=event["name"],
                value=event["value"],
            )
            return encoder.encode(ev)

        else:
            # Unknown event type, use JSON fallback
            return _encode_json_event(event)

    except ImportError:
        # ag-ui library not available, use JSON fallback
        return _encode_json_event(event)


def _encode_json_event(event: dict[str, Any]) -> str:
    """Encode event as JSON (fallback method).

    Args:
        event: Event dict to encode.

    Returns:
        SSE formatted event string with JSON payload.
    """
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
