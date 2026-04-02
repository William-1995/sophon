"""String enums for SSE and async lifecycle events (AG-UI aligned where applicable)."""

from enum import Enum


class EventType(str, Enum):
    """Canonical event ``type`` field values for streams and broadcasts.

    Members mix AG-UI run/message names and Sophon-specific tool/HITL events.
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

    # Todos (plan-first execution)
    TODOS_PLAN = "TODOS_PLAN"
    TODOS_UPDATED = "TODOS_UPDATED"


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
TODOS_PLAN = EventType.TODOS_PLAN
TODOS_UPDATED = EventType.TODOS_UPDATED
