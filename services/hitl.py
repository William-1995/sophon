"""Human-in-the-loop (HITL) helpers for decision-required events.

Also re-exports ``submit_decision`` and ``wait_for_decision`` from
``services.state`` for call sites that prefer a single ``services.hitl`` import.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from api.schemas.event_types import DECISION_REQUIRED
from services.state import broadcast_event
logger = logging.getLogger(__name__)

_DECISION_TIMEOUT = 300.0


def build_decision_event(
    run_id: str,
    message: str,
    choices: list[str],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a ``DECISION_REQUIRED`` payload without broadcasting.

    Args:
        run_id (str): Active run id.
        message (str): Prompt shown to the user.
        choices (list[str]): Allowed answers.
        payload (dict[str, Any] | None): Optional extra UI fields.

    Returns:
        Event dict suitable for SSE or internal queues.
    """
    event: dict[str, Any] = {
        "type": DECISION_REQUIRED.value,
        "runId": run_id,
        "message": message,
        "choices": choices,
    }
    if payload:
        event["payload"] = payload
    return event


def emit_decision_required(
    run_id: str,
    message: str,
    choices: list[str],
    payload: dict[str, Any] | None = None,
    stream_queue: asyncio.Queue | None = None,
) -> None:
    """Broadcast ``DECISION_REQUIRED`` and optionally mirror it to a stream queue.

    Args:
        run_id (str): Active run id.
        message (str): User-facing prompt.
        choices (list[str]): Allowed answers.
        payload (dict[str, Any] | None): Optional extra UI fields.
        stream_queue (asyncio.Queue | None): When set, ``put_nowait`` the same event.
    """
    event = build_decision_event(run_id, message, choices, payload)
    logger.info("[hitl] emit DECISION_REQUIRED run_id=%s choices=%s", run_id, choices)
    broadcast_event(event)
    if stream_queue:
        try:
            stream_queue.put_nowait(event)
        except Exception as e:
            logger.warning("[hitl] stream_queue put failed: %s", e)


async def wait_for_confirmation(
    run_id: str,
    message: str,
    choices: list[str],
    payload: dict[str, Any] | None = None,
    stream_queue: asyncio.Queue | None = None,
) -> str:
    """Emit the decision event then wait for the user's choice (with timeout).

    Args:
        run_id (str): Active run id.
        message (str): User-facing prompt.
        choices (list[str]): Allowed answers.
        payload (dict[str, Any] | None): Optional extra UI fields.
        stream_queue (asyncio.Queue | None): Optional secondary delivery queue.

    Returns:
        The submitted choice string.

    Raises:
        asyncio.TimeoutError: When no decision arrives within the internal timeout.
    """
    emit_decision_required(run_id, message, choices, payload, stream_queue)
    from services.state import _wait_for_decision_queue

    return await _wait_for_decision_queue(run_id, _DECISION_TIMEOUT)


from services.state import submit_decision, wait_for_decision  # noqa: E402, F401
