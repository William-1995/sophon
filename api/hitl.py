"""
HITL (Human-in-the-Loop) - Event-based confirmation API.

Central module for any flow that requires user confirmation:
- Delete file, risky action, etc.
- Emits standardized DECISION_REQUIRED event to all subscribers
- Waits for user choice via POST /api/runs/{run_id}/decision
"""

import asyncio
import logging
from typing import Any

from api.event_types import DECISION_REQUIRED
from api.state import broadcast_event

logger = logging.getLogger(__name__)

_DECISION_TIMEOUT = 300.0


def build_decision_event(
    run_id: str,
    message: str,
    choices: list[str],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build standardized DECISION_REQUIRED event payload."""
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
    """Emit DECISION_REQUIRED to all subscribers (broadcast + optional stream queue).

    Use stream_queue when the client consumes from a dedicated stream (sync mode)
    to guarantee delivery even if broadcast subscribers differ.
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
    """Emit DECISION_REQUIRED and wait for user choice. Use stream_queue for sync stream."""
    emit_decision_required(run_id, message, choices, payload, stream_queue)
    from api.state import _wait_for_decision_queue
    return await _wait_for_decision_queue(run_id, _DECISION_TIMEOUT)


# Re-export for callers that don't need stream_queue
from api.state import submit_decision, wait_for_decision  # noqa: E402, F401
