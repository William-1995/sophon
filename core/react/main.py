"""
ReAct Main - Core ReAct loop orchestration.

Coordinates the main ReAct execution flow: preparation, rounds, and finalization.
"""

import json
import logging
from pathlib import Path
from typing import Any

from config import get_config
from constants import DEFAULT_MAX_ROUNDS
from core.agent_loop import parse_tool_calls
from core.react.context import ImmutableRunContext, MutableRunState
from core.react.execution import (
    check_cancel_after_tools,
    execute_tool_calls_batch,
    merge_round_into_state,
)
from core.react.finalization import append_round_and_evaluate, finalize_react_answer
from core.react.preparation import prepare_react_run
from core.react.utils import (
    dedupe_references,
    emit_progress,
    extract_and_emit_thinking,
    extract_direct_answer,
    save_cancel_checkpoint,
    truncate_observations_for_llm,
)
from providers import BaseProvider

logger = logging.getLogger(__name__)


def parse_native_tool_call(raw_item: dict) -> tuple[str, str, dict, str | None]:
    """Parse native tool call into standardized format.

    Args:
        raw_item: Raw tool call dict from LLM response.

    Returns:
        Tuple of (name, tool, arguments, display_summary).
    """
    fn = raw_item.get("function") or {}
    raw_fn_name = fn.get("name", "")
    name, _, fn_action = raw_fn_name.partition(".") if "." in raw_fn_name else (raw_fn_name, "", "")
    try:
        args = json.loads(fn.get("arguments", "{}"))
    except json.JSONDecodeError:
        args = {}
    tool = str(args.pop("tool", args.pop("action", fn_action or "list"))).strip() or "list"
    display_summary = args.pop("display_summary", None)
    if isinstance(display_summary, str):
        display_summary = display_summary.strip() or None
    arguments = args.get("arguments", args)
    arguments = arguments if isinstance(arguments, dict) else {}
    return (name, tool, arguments, display_summary)


def parse_single_tool_call(
    raw_name: str,
    raw_tool: str | None,
    raw_item: dict,
    from_native_tool_calls: bool,
) -> tuple[str, str, dict, str | None] | None:
    """Parse one tool call item into standardized format.

    Args:
        raw_name: Skill name.
        raw_tool: Tool/action name.
        raw_item: Raw tool call item.
        from_native_tool_calls: Whether from native tool_calls or parsed chain.

    Returns:
        Parsed tuple or None if invalid.
    """
    import json

    if from_native_tool_calls:
        name, tool, arguments, display_summary = parse_native_tool_call(raw_item)
    else:
        args = dict(raw_item.get("arguments", {}) or {}) if isinstance(raw_item.get("arguments"), dict) else {}
        name = raw_name
        tool = raw_tool or "list"
        display_summary = args.pop("display_summary", None) or raw_item.get("display_summary")
        if isinstance(display_summary, str):
            display_summary = display_summary.strip() or None
        arguments = args
    return None if not name else (name, tool, arguments, display_summary)


def resolve_call_items(
    resp: dict,
    tools: list,
    round_num: int,
) -> list[tuple[str, str | None, dict]] | None:
    """Resolve tool call items from native tool_calls or parsed chain.

    Args:
        resp: LLM response dict.
        tools: Available tools.
        round_num: Current round number.

    Returns:
        List of call items or None if no tool calls.
    """
    tool_calls = resp.get("tool_calls", [])
    direct, chain = parse_tool_calls(resp.get("content", ""))
    effective_chain = chain if tools else []

    if tool_calls:
        return [((tc.get("function") or {}).get("name", ""), None, tc) for tc in tool_calls]
    if effective_chain:
        logger.debug("round=%d parsed chain: %s", round_num, effective_chain)
        return [(item.get("name", ""), item.get("tool", "list"), item) for item in effective_chain]
    return None


def process_llm_response(
    resp: dict,
    tools: list,
    observations: list[str],
    round_num: int,
) -> tuple[list[tuple[str, str, dict, str | None]] | None, str | None]:
    """Process LLM response to extract tool calls or direct answer.

    Args:
        resp: LLM response dict.
        tools: Available tools.
        observations: Current observations.
        round_num: Current round number.

    Returns:
        Tuple of (calls, direct_answer).
    """
    import json

    content = resp.get("content", "")
    tool_calls = resp.get("tool_calls", [])
    logger.debug("round=%d tool_calls=%d content_len=%d", round_num, len(tool_calls), len(content or ""))

    call_items = resolve_call_items(resp, tools, round_num)
    if call_items is None:
        if observations:
            logger.info("round=%d: no tools, have observations -> summarize", round_num)
        direct, _ = parse_tool_calls(content)
        ans = extract_direct_answer((direct or content) or "")
        return (None, ans) if ans else (None, None)

    parsed = [
        parse_single_tool_call(n, t, i, from_native_tool_calls=bool(tool_calls))
        for n, t, i in call_items
    ]
    calls = [x for x in parsed if x is not None]
    for name, tool, arguments, display_summary in calls:
        logger.debug("tool_call: skill=%s tool=%s arguments=%s display_summary=%s", name, tool, arguments, display_summary)
    return (calls if calls else None, None)


def get_round_action(
    resp: dict,
    tools: list,
    observations: list[str],
    round_num: int,
) -> tuple[str, str | None, list[tuple[str, str, dict, str | None]] | None]:
    """Process LLM response and determine next action.

    Args:
        resp: LLM response dict.
        tools: Available tools.
        observations: Current observations.
        round_num: Current round number.

    Returns:
        Tuple of (action, direct_answer, calls).
        action is 'direct', 'break', or 'run_tools'.
    """
    calls, direct_answer = process_llm_response(resp, tools, observations, round_num)
    n_calls = len(calls) if calls else 0
    logger.info(
        "[react] round=%d tool_calls=%d direct_answer=%s",
        round_num, n_calls, bool(direct_answer),
    )
    print(
        f"[react] round={round_num} tool_calls={n_calls} direct_answer={bool(direct_answer)}",
        flush=True,
    )
    if calls:
        parsed = [(c[0], c[1]) for c in calls]
        print(f"[react] round={round_num} executing_tools {parsed}", flush=True)
        for name, tool, args, _ in calls:
            print(
                f"[react]   -> {name}.{tool} args_keys={list(args.keys()) if isinstance(args, dict) else '?'}",
                flush=True,
            )
    if direct_answer:
        return ("direct", direct_answer, None)
    if calls is None:
        return ("break", None, None)
    return ("run_tools", None, calls)


def check_cancel_at_round_start(
    cancel_check: Any,
    ctx: ImmutableRunContext,
    state: MutableRunState,
    round_num: int,
    run_id: str | None,
) -> bool:
    """Check if cancellation was requested at round start.

    Args:
        cancel_check: Cancellation check callback.
        ctx: Immutable run context.
        state: Mutable run state.
        round_num: Current round number.
        run_id: Optional run identifier.

    Returns:
        True if cancelled.
    """
    if not cancel_check or not cancel_check():
        return False
    if ctx.db.exists():
        save_cancel_checkpoint(
            ctx.db, ctx.session_id, run_id, round_num,
            ctx.modified_question, state.observations, state.total_tokens,
            messages=ctx.messages,
        )
    state.cancelled = True
    state.resumable = True  # Checkpoint saved; user can resume
    return True


async def run_llm_round_and_count_tokens(
    provider: BaseProvider,
    ctx: ImmutableRunContext,
    round_num: int,
    event_sink: Any,
    progress_callback: Any,
    state: MutableRunState,
) -> dict:
    """Call LLM, extract thinking, count tokens, log, emit progress.

    Args:
        provider: LLM provider.
        ctx: Immutable run context.
        round_num: Current round number.
        event_sink: Optional event emission callback.
        progress_callback: Optional progress callback.
        state: Mutable run state.

    Returns:
        LLM response dict.
    """
    from db.logs import insert as log_insert

    if ctx.db.exists():
        log_insert(ctx.db, "INFO", f"llm_call round={round_num}", ctx.session_id)
    logger.debug(
        "llm_call round=%d tools_count=%d tool_names=%s",
        round_num, len(ctx.tools), [t.get("function", {}).get("name") for t in ctx.tools],
    )
    try:
        resp = await provider.chat(
            ctx.messages, tools=ctx.tools, system_prompt=ctx.system
        )
    except Exception as e:
        if ctx.db.exists():
            log_insert(
                ctx.db, "ERROR", f"llm_call_failed round={round_num}: {e}",
                ctx.session_id, {"error": str(e)},
            )
        raise
    content = resp.get("content", "")
    if event_sink and get_config().react.thinking_enabled:
        content = extract_and_emit_thinking(content, event_sink)
    resp = {**resp, "content": content}
    usage = resp.get("usage", {})
    tok = usage.get("total_tokens", 0) or (
        usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
    )
    state.total_tokens += tok
    if ctx.db.exists():
        log_insert(
            ctx.db, "INFO", f"llm_response round={round_num} tokens={tok}",
            ctx.session_id, {"tokens": tok},
        )
    emit_progress(progress_callback, state.total_tokens, round_num)
    return resp


async def run_react_rounds(
    provider: BaseProvider,
    ctx: ImmutableRunContext,
    state: MutableRunState,
    cancel_check: Any,
    progress_callback: Any,
    event_sink: Any,
    run_id: str | None,
    decision_waiter: Any,
) -> None:
    """Run ReAct round loop. Mutates ctx.messages and state.

    Args:
        provider: LLM provider.
        ctx: Immutable run context.
        state: Mutable run state.
        cancel_check: Optional cancellation check.
        progress_callback: Optional progress callback.
        event_sink: Optional event emission callback.
        run_id: Optional run identifier.
        decision_waiter: Optional HITL decision waiter.
    """
    for round_num in range(ctx.start_round, DEFAULT_MAX_ROUNDS + 1):
        if check_cancel_at_round_start(
            cancel_check, ctx, state, round_num, run_id
        ):
            return
        resp = await run_llm_round_and_count_tokens(
            provider, ctx, round_num, event_sink, progress_callback, state
        )
        action, direct_answer, calls = get_round_action(
            resp, ctx.tools, state.observations, round_num
        )
        if action == "direct":
            state.answer_from_skill = direct_answer
            return
        if action == "break":
            ctx.messages.append({"role": "assistant", "content": resp.get("content", "")})
            return

        obs_list, gu, direct, refs, abort_run = await execute_tool_calls_batch(
            calls,
            ctx.workspace_root,
            ctx.session_id,
            ctx.user_id,
            ctx.db,
            get_config().react.max_parallel_tool_calls,
            event_sink=event_sink,
            run_id=run_id,
            decision_waiter=decision_waiter,
        )
        if check_cancel_after_tools(
            cancel_check, ctx, state, round_num, run_id, resp, obs_list
        ):
            return
        if abort_run:
            logger.info("[react] early exit requested by skill run_id=%s", run_id)
            merge_round_into_state(state, obs_list, gu, direct, refs)
            state.cancelled = True
            return
        merge_round_into_state(state, obs_list, gu, direct, refs)
        satisfied = await append_round_and_evaluate(
            ctx, state, resp, provider, progress_callback, round_num
        )
        if satisfied:
            return


async def run_react(
    question: str,
    provider: BaseProvider,
    workspace_root: Path,
    session_id: str = "default",
    user_id: str = "default_user",
    skill_filter: str | None = None,
    context: list[dict] | None = None,
    db_path: Path | None = None,
    progress_callback: Any = None,
    system_prompt_override: str | None = None,
    event_sink: Any = None,
    run_id: str | None = None,
    cancel_check: Any = None,
    decision_waiter: Any = None,
    resume_checkpoint: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Run ReAct loop. Returns (answer_text, metadata).

    Args:
        question: User question.
        provider: LLM provider.
        workspace_root: Workspace root path.
        session_id: Session ID.
        user_id: User ID.
        skill_filter: If set, restrict to this skill (skip round-1 selection).
        context: Conversation context (recent messages).
        db_path: Optional DB path.
        progress_callback: Called after each LLM call with (tokens, round_num).
        system_prompt_override: Prepended to system prompt.
        event_sink: Receives TOOL_START/TOOL_END etc.; run_id tags the run.
        run_id: Run identifier.
        cancel_check: If True, exit at step boundary; metadata includes cancelled=True.
        decision_waiter: For HITL tool (request_human_decision).
        resume_checkpoint: When provided, continue from saved state.

    Returns:
        (answer_text, metadata) with keys tokens, cache_hit, gen_ui, references,
        and optionally cancelled, modified_question.
    """
    ctx, state = await prepare_react_run(
        question=question,
        provider=provider,
        workspace_root=workspace_root,
        session_id=session_id,
        user_id=user_id,
        skill_filter=skill_filter,
        context=context,
        db_path=db_path,
        system_prompt_override=system_prompt_override,
        resume_checkpoint=resume_checkpoint,
        run_id=run_id,
        decision_waiter=decision_waiter,
    )
    await run_react_rounds(
        provider=provider,
        ctx=ctx,
        state=state,
        cancel_check=cancel_check,
        progress_callback=progress_callback,
        event_sink=event_sink,
        run_id=run_id,
        decision_waiter=decision_waiter,
    )
    if state.cancelled:
        return "[Run cancelled by user.]", {
            "tokens": state.total_tokens,
            "cache_hit": False,
            "gen_ui": state.gen_ui_collected,
            "references": list(state.all_references),
            "cancelled": True,
            "resumable": state.resumable,
        }
    final_answer, total_tokens = await finalize_react_answer(
        ctx=ctx, state=state, provider=provider,
    )
    state.total_tokens = total_tokens
    emit_progress(progress_callback, total_tokens, 0)
    deduped_refs = dedupe_references(state.all_references)
    return final_answer, {
        "tokens": total_tokens,
        "cache_hit": False,
        "gen_ui": state.gen_ui_collected,
        "references": deduped_refs,
        "modified_question": ctx.modified_question,
    }
