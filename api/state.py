"""
API State Management - Global state for the FastAPI application.

Provides centralized state management for:
- Event broadcasting to SSE clients
- Run cancellation tracking
- Human-in-the-loop (HITL) decision queues

All state is module-level and should be accessed through the provided functions
to ensure proper encapsulation.
"""

import asyncio
import logging
from typing import Any

from api.event_types import DECISION_REQUIRED

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state (private)
# ---------------------------------------------------------------------------

# Global event bus for async task lifecycle (TASK_STARTED / TASK_FINISHED / TASK_ERROR).
# Each subscriber has a queue for event delivery.
_event_subscribers: list[asyncio.Queue] = []

# Cancel requested per run_id (stream runs).
# When set, run_react should stop at next step boundary.
_cancel_requested: dict[str, asyncio.Event] = {}

# Sentinel: never set, so cancel_check() is False when run_id not in _cancel_requested.
_cancel_never: asyncio.Event = asyncio.Event()

# HITL: per run_id queue for user decisions.
# POST /api/runs/{run_id}/decision puts the choice here.
_decision_queues: dict[str, asyncio.Queue] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def broadcast_event(event: dict[str, Any]) -> None:
    """Push event to all connected SSE clients (non-blocking).

    Removes dead queues (where put_nowait raises an exception).

    Args:
        event: Event dict to broadcast to all subscribers.
    """
    dead: list[asyncio.Queue] = []
    for queue in _event_subscribers:
        try:
            queue.put_nowait(event)
        except Exception:
            dead.append(queue)

    # Clean up dead subscribers
    for queue in dead:
        try:
            _event_subscribers.remove(queue)
        except ValueError:
            pass


def request_cancel(run_id: str) -> None:
    """Request cancellation of a streaming run.

    The cancellation takes effect at the next step boundary.

    Args:
        run_id: Run identifier to cancel.
    """
    if run_id in _cancel_requested:
        _cancel_requested[run_id].set()


def is_cancelled(run_id: str) -> bool:
    """Check if a run has been cancelled.

    Args:
        run_id: Run identifier to check.

    Returns:
        True if the run has been cancelled.
    """
    return _cancel_requested.get(run_id, _cancel_never).is_set()


def create_cancel_event(run_id: str) -> None:
    """Create a cancel event for a new run.

    Args:
        run_id: Run identifier to create cancel event for.
    """
    _cancel_requested[run_id] = asyncio.Event()


def cleanup_cancel_event(run_id: str) -> None:
    """Remove cancel event for a completed run.

    Args:
        run_id: Run identifier to clean up.
    """
    _cancel_requested.pop(run_id, None)


def add_event_subscriber() -> asyncio.Queue:
    """Add a new event subscriber and return its queue.

    Returns:
        New asyncio.Queue for receiving events.
    """
    queue: asyncio.Queue = asyncio.Queue()
    _event_subscribers.append(queue)
    return queue


def remove_event_subscriber(queue: asyncio.Queue) -> None:
    """Remove an event subscriber.

    Args:
        queue: Queue to remove from subscribers.
    """
    try:
        _event_subscribers.remove(queue)
    except ValueError:
        pass


async def submit_decision(run_id: str, choice: str) -> None:
    """Submit a user decision for HITL.

    Args:
        run_id: Run identifier.
        choice: User's selected choice.
    """
    if run_id not in _decision_queues:
        _decision_queues[run_id] = asyncio.Queue()
    try:
        _decision_queues[run_id].put_nowait(choice)
    except asyncio.QueueFull:
        logger.warning("Decision queue full for run_id=%s", run_id)


async def wait_for_decision(
    run_id: str,
    message: str,
    choices: list[str],
    payload: dict[str, Any] | None = None,
) -> str:
    """Wait for a user decision via HITL.

    Emits DECISION_REQUIRED event and waits for user response.

    Args:
        run_id: Run identifier.
        message: Question or context for the user.
        choices: List of available choices.
        payload: Optional extra data (e.g. {"files": [...]}) for frontend display.

    Returns:
        The user's selected choice.

    Raises:
        asyncio.TimeoutError: If user does not respond within timeout.
    """
    event: dict[str, Any] = {
        "type": DECISION_REQUIRED.value,
        "runId": run_id,
        "message": message,
        "choices": choices,
    }
    if payload:
        event["payload"] = payload
    logger.info("[hitl] emit DECISION_REQUIRED run_id=%s choices=%s", run_id, choices)
    broadcast_event(event)

    if run_id not in _decision_queues:
        _decision_queues[run_id] = asyncio.Queue()

    try:
        return await asyncio.wait_for(_decision_queues[run_id].get(), timeout=300.0)
    finally:
        # Clean up decision queue
        _decision_queues.pop(run_id, None)
