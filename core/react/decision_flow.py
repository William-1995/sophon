"""
HITL two-phase flow for tools that return __decision_request.

Used by filesystem skills (subprocess) and built-in task_plan (in-process).
Orchestration resolves the user choice once; re-invocation is supplied by the caller.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from config import get_config
from constants import ABORT_RUN_KEY
from constants import DECISION_PAYLOAD_AUTO_CONFIRM_IF_PLAN_CONFIRMED, DECISION_REQUEST_KEY
from core.react.context import MutableRunState
from core.react.types import DecisionWaiter

logger = logging.getLogger(__name__)


async def wait_for_user_choice(
    dr: dict[str, Any],
    *,
    state: MutableRunState | None,
    decision_waiter: DecisionWaiter | None,
) -> tuple[str, dict[str, Any]]:
    """Resolve choice from __decision_request; return (choice, payload dict)."""
    dr_payload = dr.get("payload") if isinstance(dr.get("payload"), dict) else {}
    auto_confirm = (
        state is not None
        and state.plan_confirmed
        and dr_payload.get(DECISION_PAYLOAD_AUTO_CONFIRM_IF_PLAN_CONFIRMED) is True
    )
    if auto_confirm:
        choices = dr.get("choices") or []
        choice = "Confirm" if "Confirm" in choices else (str(choices[0]) if choices else "")
        logger.info("[react] plan_confirmed + payload auto_confirm flag, choice=%r", choice)
    elif decision_waiter:
        payload = dr_payload or None
        timeout = get_config().react.hitl_timeout_seconds
        choice = await asyncio.wait_for(
            decision_waiter(
                str(dr["message"]),
                [str(c) for c in dr["choices"]],
                payload=payload if isinstance(payload, dict) else None,
            ),
            timeout=timeout,
        )
    else:
        choice = str(dr["choices"][0]) if dr["choices"] else ""
    return choice, dr_payload


def merge_decision_args(
    arguments: dict[str, Any],
    choice: str,
    dr_payload: dict[str, Any],
) -> dict[str, Any]:
    """Build second-phase arguments: _decision_choice + optional _decision_plan_snapshot."""
    merged = dict(arguments, _decision_choice=choice)
    plan_snap = dr_payload.get("plan")
    if isinstance(plan_snap, list) and plan_snap:
        merged["_decision_plan_snapshot"] = plan_snap
    return merged


async def run_two_phase(
    arguments: dict[str, Any],
    *,
    state: MutableRunState | None,
    decision_waiter: DecisionWaiter | None,
    run_once: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    """Run tool once; if __decision_request, wait for choice and run_once again with merged args."""
    result = await run_once(arguments)
    dr = result.get(DECISION_REQUEST_KEY)
    if not isinstance(dr, dict) or not dr.get("message") or not dr.get("choices"):
        return result
    choice, dr_payload = await wait_for_user_choice(dr, state=state, decision_waiter=decision_waiter)
    if str(choice).strip().lower() == "cancel":
        logger.info("[react] decision cancelled, short-circuiting run_once rerun")
        cancelled = dict(result)
        cancelled[ABORT_RUN_KEY] = True
        cancelled["cancelled"] = True
        cancelled["observation"] = str(dr_payload.get("message") or "User cancelled the request.")
        return cancelled
    merged = merge_decision_args(arguments, choice, dr_payload)
    return await run_once(merged)
