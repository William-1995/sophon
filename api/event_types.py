"""
Event Types - Enumeration of all event types used in the API.

Provides type-safe event type definitions for SSE streaming and async task lifecycle.
"""

from enum import Enum


class EventType(str, Enum):
    """Enumeration of all event types.

    Used for SSE streaming and async task lifecycle events.
    All values are lowercase strings for consistency with AG-UI protocol.
    """

    # Task lifecycle events
    TASK_STARTED = "TASK_STARTED"
    TASK_FINISHED = "TASK_FINISHED"
    TASK_ERROR = "TASK_ERROR"

    # Run lifecycle events (AG-UI compatible)
    RUN_STARTED = "RUN_STARTED"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_ERROR = "RUN_ERROR"
    RUN_CANCELLED = "RUN_CANCELLED"

    # Message events (AG-UI compatible)
    TEXT_MESSAGE_START = "TEXT_MESSAGE_START"
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    TEXT_MESSAGE_END = "TEXT_MESSAGE_END"

    # Custom events
    CUSTOM = "CUSTOM"
    HEARTBEAT = "heartbeat"

    # HITL events
    DECISION_REQUIRED = "DECISION_REQUIRED"

    # Thinking events
    THINKING = "THINKING"

    # Tool events
    TOOL_START = "TOOL_START"
    TOOL_END = "TOOL_END"

    # Emotion events (orb ring)
    EMOTION_UPDATED = "EMOTION_UPDATED"


# ---------------------------------------------------------------------------
# Event type aliases for backward compatibility
# ---------------------------------------------------------------------------

TASK_STARTED = EventType.TASK_STARTED
TASK_FINISHED = EventType.TASK_FINISHED
TASK_ERROR = EventType.TASK_ERROR
RUN_STARTED = EventType.RUN_STARTED
RUN_FINISHED = EventType.RUN_FINISHED
RUN_ERROR = EventType.RUN_ERROR
RUN_CANCELLED = EventType.RUN_CANCELLED
TEXT_MESSAGE_START = EventType.TEXT_MESSAGE_START
TEXT_MESSAGE_CONTENT = EventType.TEXT_MESSAGE_CONTENT
TEXT_MESSAGE_END = EventType.TEXT_MESSAGE_END
CUSTOM = EventType.CUSTOM
HEARTBEAT = EventType.HEARTBEAT
DECISION_REQUIRED = EventType.DECISION_REQUIRED
THINKING = EventType.THINKING
TOOL_START = EventType.TOOL_START
TOOL_END = EventType.TOOL_END
EMOTION_UPDATED = EventType.EMOTION_UPDATED
