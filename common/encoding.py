"""Encode internal event dicts to AG-UI SSE lines, with JSON fallback."""

import json
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def encode_ag_ui_event(event: dict[str, Any]) -> str:
    """Encode one logical event to a single SSE payload line.

    Uses ``ag_ui`` encoder classes when importable; unknown types use JSON.

    Args:
        event (dict[str, Any]): Must include ``type``; other keys vary by type
            (``RUN_*``, ``TEXT_MESSAGE_*``, ``CUSTOM``, etc.).

    Returns:
        A string suitable for ``StreamingResponse`` (includes ``data:`` prefix
        and trailing blank line from encoder or ``_encode_json_event``).
    """
    try:
        return _encode_with_ag_ui(event)
    except ImportError:
        return _encode_json_event(event)


def _encode_with_ag_ui(event: dict[str, Any]) -> str:
    """Encode known event shapes with ag-ui classes."""
    from ag_ui.core import EventType
    from ag_ui.encoder import EventEncoder

    encoder = EventEncoder()
    event_type = event.get("type")

    handlers: dict[str, Callable[[], str]] = {
        "RUN_STARTED": lambda: _encode_run_started(encoder, EventType, event),
        "RUN_FINISHED": lambda: _encode_run_finished(encoder, EventType, event),
        "RUN_ERROR": lambda: _encode_run_error(encoder, EventType, event),
        "TEXT_MESSAGE_START": lambda: _encode_text_message_start(encoder, EventType, event),
        "TEXT_MESSAGE_CONTENT": lambda: _encode_text_message_content(encoder, EventType, event),
        "TEXT_MESSAGE_END": lambda: _encode_text_message_end(encoder, EventType, event),
        "CUSTOM": lambda: _encode_custom(encoder, EventType, event),
        "RUN_CANCELLED": lambda: _encode_json_event(event),
    }

    handler = handlers.get(event_type)
    if handler is None:
        return _encode_json_event(event)
    return handler()


def _encode_run_started(encoder: Any, event_type: Any, event: dict[str, Any]) -> str:
    from ag_ui.core import RunStartedEvent

    ev = RunStartedEvent(
        type=event_type.RUN_STARTED,
        thread_id=event["threadId"],
        run_id=event["runId"],
    )
    return encoder.encode(ev)


def _encode_run_finished(encoder: Any, event_type: Any, event: dict[str, Any]) -> str:
    from ag_ui.core import RunFinishedEvent

    ev = RunFinishedEvent(
        type=event_type.RUN_FINISHED,
        thread_id=event["threadId"],
        run_id=event["runId"],
        result=event.get("result"),
    )
    return encoder.encode(ev)


def _encode_run_error(encoder: Any, event_type: Any, event: dict[str, Any]) -> str:
    from ag_ui.core import RunErrorEvent

    ev = RunErrorEvent(
        type=event_type.RUN_ERROR,
        message=event["message"],
    )
    return encoder.encode(ev)


def _encode_text_message_start(encoder: Any, event_type: Any, event: dict[str, Any]) -> str:
    from ag_ui.core import TextMessageStartEvent

    ev = TextMessageStartEvent(
        type=event_type.TEXT_MESSAGE_START,
        message_id=event["messageId"],
        role="assistant",
    )
    return encoder.encode(ev)


def _encode_text_message_content(encoder: Any, event_type: Any, event: dict[str, Any]) -> str:
    from ag_ui.core import TextMessageContentEvent

    ev = TextMessageContentEvent(
        type=event_type.TEXT_MESSAGE_CONTENT,
        message_id=event["messageId"],
        delta=event["delta"],
    )
    return encoder.encode(ev)


def _encode_text_message_end(encoder: Any, event_type: Any, event: dict[str, Any]) -> str:
    from ag_ui.core import TextMessageEndEvent

    ev = TextMessageEndEvent(
        type=event_type.TEXT_MESSAGE_END,
        message_id=event["messageId"],
    )
    return encoder.encode(ev)


def _encode_custom(encoder: Any, event_type: Any, event: dict[str, Any]) -> str:
    from ag_ui.core import CustomEvent

    ev = CustomEvent(
        type=event_type.CUSTOM,
        name=event["name"],
        value=event["value"],
    )
    return encoder.encode(ev)


def _encode_json_event(event: dict[str, Any]) -> str:
    """Serialize ``event`` as UTF-8 JSON inside one SSE data field.

    Args:
        event (dict[str, Any]): Any JSON-serializable event payload.

    Returns:
        ``data: {...}\n\n`` string.
    """
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
