"""In-process registries for SSE broadcast, run cancellation, and HITL queues.

Mutable state lives in private module globals; use the functions in this module
rather than importing those containers directly.
"""

import asyncio
import logging
from typing import Any

from api.schemas.event_types import DECISION_REQUIRED

logger = logging.getLogger(__name__)

# Global event bus: TASK_STARTED / TASK_FINISHED / TASK_ERROR per subscriber queue.
_event_subscribers: list[asyncio.Queue] = []

# Per run_id cancel flag for streaming runs (``run_react`` polls ``cancel_check``).
_cancel_requested: dict[str, asyncio.Event] = {}

# Sentinel so ``is_cancelled`` is False when ``run_id`` is unknown.
_cancel_never: asyncio.Event = asyncio.Event()

# HITL: POST /api/runs/{run_id}/decision delivers choices here.
_decision_queues: dict[str, asyncio.Queue] = {}


def broadcast_event(event: dict[str, Any]) -> None:
    """Push an event to every registered SSE subscriber (non-blocking).

    Queues that raise on ``put_nowait`` are removed from the subscriber list.

    Args:
        event (dict[str, Any]): Payload copied to each subscriber queue.
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
    """Signal that a streaming run should stop at the next safe boundary.

    Args:
        run_id (str): Run identifier previously passed to ``create_cancel_event``.
    """
    if run_id in _cancel_requested:
        _cancel_requested[run_id].set()


def is_cancelled(run_id: str) -> bool:
    """Return whether ``request_cancel`` has been called for this run.

    Args:
        run_id (str): Run identifier.

    Returns:
        True if the cancel event is set.
    """
    return _cancel_requested.get(run_id, _cancel_never).is_set()


def create_cancel_event(run_id: str) -> None:
    """Allocate a fresh ``asyncio.Event`` for cancel tracking for a new run.

    Args:
        run_id (str): New run identifier.
    """
    _cancel_requested[run_id] = asyncio.Event()


def cleanup_cancel_event(run_id: str) -> None:
    """Drop cancel state after a run finishes so IDs can be reused safely.

    Args:
        run_id (str): Run identifier to remove.
    """
    _cancel_requested.pop(run_id, None)


def add_event_subscriber() -> asyncio.Queue:
    """Register a subscriber queue for the global async-task event bus.

    Returns:
        asyncio.Queue: New queue receiving ``broadcast_event`` payloads.
    """
    queue: asyncio.Queue = asyncio.Queue()
    _event_subscribers.append(queue)
    return queue


def remove_event_subscriber(queue: asyncio.Queue) -> None:
    """Unregister a queue previously returned by ``add_event_subscriber``.

    Args:
        queue (asyncio.Queue): Same queue instance returned by ``add_event_subscriber``.
    """
    try:
        _event_subscribers.remove(queue)
    except ValueError:
        pass


async def submit_decision(run_id: str, choice: str) -> None:
    """Deliver the user's HITL choice to the waiter for ``run_id``.

    Args:
        run_id (str): Run identifier from ``DECISION_REQUIRED``.
        choice (str): Label matching one of the offered choices.
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
    """Emit ``DECISION_REQUIRED`` on the bus, then wait for ``submit_decision``.

    Args:
        run_id (str): Run identifier.
        message (str): Prompt for the user.
        choices (list[str]): Allowed answers.
        payload (dict[str, Any] | None): Optional extra fields for the client UI.

    Returns:
        The submitted choice string.

    Raises:
        asyncio.TimeoutError: If no choice arrives within 300 seconds.
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


async def _wait_for_decision_queue(run_id: str, timeout: float) -> str:
    """Wait for ``submit_decision`` without emitting another ``DECISION_REQUIRED``.

    Used by ``api.hitl`` after events were already sent on the stream / bus.

    Args:
        run_id (str): Run identifier.
        timeout (float): Seconds to wait for a choice.

    Returns:
        The user's selected choice string.

    Raises:
        asyncio.TimeoutError: If no choice is submitted in time.
    """
    if run_id not in _decision_queues:
        _decision_queues[run_id] = asyncio.Queue()
    try:
        return await asyncio.wait_for(_decision_queues[run_id].get(), timeout=timeout)
    finally:
        _decision_queues.pop(run_id, None)
