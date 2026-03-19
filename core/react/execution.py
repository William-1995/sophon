"""
ReAct Execution - Tool call execution and HITL handling.

Handles parallel tool execution, event emission, and human-in-the-loop interactions.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from constants import ABORT_RUN_KEY, DECISION_REQUEST_KEY
from config import get_config
from core.react.types import CancelCheck, DecisionWaiter, EventSink
from core.agent_loop import parse_tool_calls
from core.executor import execute_skill
from core.path_lock import get_locks_for_tool_call, maybe_acquire_path_locks
from core.react.context import ImmutableRunContext, MutableRunState
from core.react.preparation import HITL_TOOL_NAME
from core.react.utils import format_skill_observation, save_cancel_checkpoint

logger = logging.getLogger(__name__)


async def execute_tool_calls_batch(
    calls: list[tuple[str, str, dict, str | None]],
    workspace_root: Path,
    session_id: str,
    user_id: str,
    db: Path,
    max_parallel: int,
    event_sink: EventSink = None,
    run_id: str | None = None,
    decision_waiter: DecisionWaiter = None,
) -> tuple[list[str], dict[str, Any] | None, str | None, list[dict], bool]:
    """Execute tool calls in parallel with semaphore.

    Args:
        calls: List of (name, tool, arguments, display_summary) tuples.
        workspace_root: Workspace root path.
        session_id: Session identifier.
        user_id: User identifier.
        db: Database path.
        max_parallel: Maximum concurrent executions.
        event_sink: Optional event emission callback.
        run_id: Optional run identifier.
        decision_waiter: Optional HITL decision waiter.

    Returns:
        Tuple of (observations, gen_ui, direct_answer, references, abort_run).
        abort_run: True when a skill returned _abort_run (early exit requested).
    """
    sem = asyncio.Semaphore(max_parallel)

    async def run_one(
        name: str, tool: str, arguments: dict, display_summary: str | None
    ) -> tuple[str, dict | None, str | None, list[dict]]:
        async with sem:
            return await execute_tool_call(
                name=name,
                tool=tool,
                arguments=arguments,
                display_summary=display_summary,
                workspace_root=workspace_root,
                session_id=session_id,
                user_id=user_id,
                db=db,
                gen_ui_collected=None,
                event_sink=event_sink,
                run_id=run_id,
                decision_waiter=decision_waiter,
            )

    results = await asyncio.gather(*[run_one(n, t, a, d) for n, t, a, d in calls])
    observations: list[str] = []
    gen_ui: dict[str, Any] | None = None
    direct_answer: str | None = None
    all_refs: list[dict] = []
    abort_run = False
    for obs, gu, ans, refs, abort in results:
        observations.append(obs)
        if gu is not None:
            gen_ui = gu
        if ans:
            direct_answer = ans
        if refs:
            all_refs.extend(refs)
        if abort:
            abort_run = True
    return observations, gen_ui, direct_answer, all_refs, abort_run


async def execute_tool_call(
    name: str,
    tool: str,
    arguments: dict,
    display_summary: str | None,
    workspace_root: Path,
    session_id: str,
    user_id: str,
    db: Path,
    gen_ui_collected: dict | None,
    event_sink: EventSink = None,
    run_id: str | None = None,
    decision_waiter: DecisionWaiter = None,
) -> tuple[str, dict | None, str | None, list[dict], bool]:
    """Execute a single skill tool call.

    Args:
        name: Skill name.
        tool: Action/tool name.
        arguments: Tool arguments.
        display_summary: Optional display summary for UI.
        workspace_root: Workspace root path.
        session_id: Session identifier.
        user_id: User identifier.
        db: Database path.
        gen_ui_collected: Optional existing gen_ui data.
        event_sink: Optional event emission callback.
        run_id: Optional run identifier.
        decision_waiter: Optional HITL decision waiter.

    Returns:
        Tuple of (observation, gen_ui, direct_answer, references, abort_run).
    """
    if name == HITL_TOOL_NAME and decision_waiter:
        ret = await handle_hitl_tool_call(name, arguments, decision_waiter, gen_ui_collected)
        return (*ret, False)  # HITL tool has no skill cancelled

    path_locks = get_locks_for_tool_call(workspace_root, name, tool, arguments)
    async with maybe_acquire_path_locks(path_locks):
        emit_tool_start(event_sink, name, tool, display_summary)
        result = await execute_skill(
            skill_name=name,
            action=tool,
            arguments=arguments,
            workspace_root=workspace_root,
            session_id=session_id,
            user_id=user_id,
            db_path=db if db.exists() else None,
            event_sink=event_sink,
            run_id=run_id,
            agent_id=name,
        )

        # Two-phase flow: skill requested user confirmation
        dr = result.get(DECISION_REQUEST_KEY)
        if isinstance(dr, dict) and dr.get("message") and dr.get("choices"):
            choice: str
            if decision_waiter:
                payload = dr.get("payload")
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
            merged = dict(arguments, _decision_choice=choice)
            result = await execute_skill(
                skill_name=name,
                action=tool,
                arguments=merged,
                workspace_root=workspace_root,
                session_id=session_id,
                user_id=user_id,
                db_path=db if db.exists() else None,
                event_sink=event_sink,
                run_id=run_id,
                agent_id=name,
            )

    emit_tool_end(event_sink, name, tool, result.get("error"))
    obs, gu, direct, refs = result_to_observation_and_extras(name, tool, result, gen_ui_collected)
    abort_run = bool(result.get(ABORT_RUN_KEY))
    if abort_run:
        logger.info("[react] skill requested early exit %s.%s run_id=%s", name, tool, run_id)
    return obs, gu, direct, refs, abort_run


async def handle_hitl_tool_call(
    name: str,
    arguments: dict,
    decision_waiter: DecisionWaiter,
    gen_ui_collected: dict | None,
) -> tuple[str, dict | None, str | None, list[dict]]:
    """Run HITL (request_human_decision) and return observation tuple.

    Args:
        name: Tool name.
        arguments: Tool arguments containing message and choices.
        decision_waiter: Decision waiter callback.
        gen_ui_collected: Optional existing gen_ui data.

    Returns:
        Observation tuple.
    """
    msg = str(arguments.get("message", ""))
    choices = arguments.get("choices") or []
    if not isinstance(choices, list):
        choices = [str(c) for c in (choices,) if c]
    else:
        choices = [str(c) for c in choices]
    try:
        timeout = get_config().react.hitl_timeout_seconds
        payload = arguments.get("payload") if isinstance(arguments.get("payload"), dict) else None
        choice = await asyncio.wait_for(
            decision_waiter(msg, choices, payload=payload),
            timeout=timeout,
        )
        obs = f"User chose: {choice}"
    except asyncio.TimeoutError:
        obs = "Decision timed out; proceeding with first option."
    except Exception as e:
        obs = f"Decision error: {e}"
    return f"[{name}]: {obs}", gen_ui_collected, None, []


def emit_tool_start(
    event_sink: EventSink,
    name: str,
    tool: str,
    display_summary: str | None,
) -> None:
    """Emit TOOL_START event with display_text; fallback to minimal payload on error."""
    if not event_sink:
        return
    display_text = (display_summary or "").strip() or f"Running {name}.{tool}"
    try:
        event_sink({
            "type": "TOOL_START",
            "skill": name,
            "action": tool,
            "agent_id": "main",
            "description": display_text,
            "display_text": display_text,
        })
    except Exception as e:
        logger.debug("[react] TOOL_START fallback: %s.%s (%s)", name, tool, e)
        try:
            event_sink({
                "type": "TOOL_START",
                "skill": name,
                "action": tool,
                "agent_id": "main",
                "display_text": f"Running {name}.{tool}",
            })
        except Exception:
            pass


def emit_tool_end(
    event_sink: EventSink,
    name: str,
    tool: str,
    error: Any,
) -> None:
    """Emit TOOL_END event."""
    if event_sink:
        try:
            event_sink({
                "type": "TOOL_END",
                "skill": name,
                "action": tool,
                "agent_id": "main",
                "error": error,
            })
        except Exception:
            pass


def collect_references_from_result(result: dict) -> list[dict]:
    """Extract unified [{title, url}] from result["references"]."""
    refs: list[dict] = []
    raw = result.get("references")
    if not isinstance(raw, list):
        return refs
    for r in raw:
        if isinstance(r, dict) and r.get("url"):
            refs.append({
                "title": str(r.get("title") or "Source"),
                "url": str(r["url"]),
            })
    return refs


def result_to_observation_and_extras(
    name: str,
    tool: str,
    result: dict,
    gen_ui_collected: dict | None,
) -> tuple[str, dict | None, str | None, list[dict]]:
    """Build (observation_str, gen_ui, direct_answer, references) from skill result."""
    obs = format_skill_observation(result)
    if result.get("error"):
        logger.warning("skill error: %s.%s -> %s", name, tool, result["error"])
    else:
        logger.debug("skill result: %s.%s -> %s", name, tool, obs[:200])
    gu = result["gen_ui"] if result.get("gen_ui") else gen_ui_collected
    ans = result.get("answer")
    direct_answer = (ans.strip() if isinstance(ans, str) and ans.strip() else None)
    refs = collect_references_from_result(result)
    return f"[{name}.{tool}]: {obs}", gu, direct_answer, refs


def check_cancel_after_tools(
    cancel_check: "CancelCheck",
    ctx: ImmutableRunContext,
    state: MutableRunState,
    round_num: int,
    run_id: str | None,
    resp: dict,
    obs_list: list[str],
) -> bool:
    """If cancel requested after tools, save checkpoint and set state.cancelled.

    Returns:
        True if cancelled.
    """
    if not cancel_check or not cancel_check():
        return False
    logger.info("[react] cancelled after tool batch run_id=%s", run_id)
    if ctx.db.exists():
        obs_extended = state.observations + obs_list
        msg_extended = ctx.messages + [
            {"role": "assistant", "content": resp.get("content", "")},
        ]
        from core.react.utils import truncate_observations_for_llm
        results_content = truncate_observations_for_llm(obs_extended)
        msg_extended.append({"role": "user", "content": results_content})
        save_cancel_checkpoint(
            ctx.db, ctx.session_id, run_id, round_num,
            ctx.modified_question, obs_extended, state.total_tokens,
            messages=msg_extended,
        )
    state.cancelled = True
    state.resumable = True  # Checkpoint saved; user can resume
    return True


def merge_round_into_state(
    state: MutableRunState,
    obs_list: list[str],
    gu: dict[str, Any] | None,
    direct: str | None,
    refs: list[dict],
) -> None:
    """Merge tool round results into state (observations, references, gen_ui, answer_from_skill)."""
    state.observations.extend(obs_list)
    state.all_references.extend(refs)
    if gu is not None:
        state.gen_ui_collected = gu
    if direct:
        state.answer_from_skill = direct
