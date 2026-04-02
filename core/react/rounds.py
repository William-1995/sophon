"""
ReAct Rounds - Round loop and LLM invocation.

Handles per-round LLM calls, cancellation checks, and tool execution.
"""

import logging
from config import get_config
from core.react.types import CancelCheck, DecisionWaiter, EventSink, ProgressCallback
from constants import AGENT_LOOP_FORCE_TOOL_MSG, DEFAULT_MAX_ROUNDS, REACT_MAX_EMPTY_TOOL_FORCE
from core.react.context import ImmutableRunContext, MutableRunState
from core.react.execution import (
    check_cancel_after_tools,
    execute_tool_calls_batch,
    merge_round_into_state,
)
from core.react.finalization import append_round_and_evaluate
from core.react.tool_parsing import get_round_action
from core.react.utils import (
    emit_progress,
    extract_and_emit_thinking,
    save_cancel_checkpoint,
)
from providers import BaseProvider

logger = logging.getLogger(__name__)


def check_cancel_at_round_start(
    cancel_check: CancelCheck,
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
    event_sink: EventSink,
    progress_callback: ProgressCallback,
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
        round_num,
        len(ctx.tools),
        [t.get("function", {}).get("name") for t in ctx.tools],
    )
    tools_for_round = (
        getattr(ctx, "compact_tools", None) if round_num > 1 else None
    ) or ctx.tools
    try:
        resp = await provider.chat(
            ctx.messages, tools=tools_for_round, system_prompt=ctx.system
        )
    except Exception as e:
        if ctx.db.exists():
            log_insert(
                ctx.db,
                "ERROR",
                f"llm_call_failed round={round_num}: {e}",
                ctx.session_id,
                {"error": str(e)},
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
            ctx.db,
            "INFO",
            f"llm_response round={round_num} tokens={tok}",
            ctx.session_id,
            {"tokens": tok, "step": "llm_round", "round": round_num},
        )
        from db.metrics import insert as metrics_insert
        metrics_insert(
            ctx.db,
            "llm_tokens",
            float(tok),
            tags={"step": "llm_round", "round": round_num, "session_id": ctx.session_id, "run_id": (ctx.run_id or "")},
        )
    emit_progress(progress_callback, state.total_tokens, round_num)
    return resp


async def run_react_rounds(
    provider: BaseProvider,
    ctx: ImmutableRunContext,
    state: MutableRunState,
    cancel_check: CancelCheck,
    progress_callback: ProgressCallback,
    event_sink: EventSink,
    run_id: str | None,
    decision_waiter: DecisionWaiter,
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
            if (
                not state.observations
                and ctx.tools
                and state.empty_tool_force_count < REACT_MAX_EMPTY_TOOL_FORCE
            ):
                state.empty_tool_force_count += 1
                ctx.messages.append({"role": "user", "content": AGENT_LOOP_FORCE_TOOL_MSG})
                logger.info(
                    "[react] round=%d: no tool_calls and no observations -> force tool (%d/%d)",
                    round_num,
                    state.empty_tool_force_count,
                    REACT_MAX_EMPTY_TOOL_FORCE,
                )
                continue
            return

        obs_list, gu, direct, refs, abort_run, skill_tokens = await execute_tool_calls_batch(
            calls,
            ctx.workspace_root,
            ctx.session_id,
            ctx.user_id,
            ctx.db,
            get_config().react.max_parallel_tool_calls,
            event_sink=event_sink,
            run_id=run_id,
            decision_waiter=decision_waiter,
            tools=ctx.tools,
            state=state,
        )
        if check_cancel_after_tools(
            cancel_check, ctx, state, round_num, run_id, resp, obs_list
        ):
            return
        if skill_tokens > 0:
            state.total_tokens += skill_tokens
            if ctx.db.exists():
                from db.logs import insert as log_insert
                from db.metrics import insert as metrics_insert
                log_insert(
                    ctx.db,
                    "INFO",
                    f"tokens step=skill tokens={skill_tokens} round={round_num}",
                    ctx.session_id,
                    {"step": "skill", "tokens": skill_tokens, "round": round_num},
                )
                metrics_insert(
                    ctx.db,
                    "llm_tokens",
                    float(skill_tokens),
                    tags={"step": "skill", "round": round_num, "session_id": ctx.session_id, "run_id": run_id or ""},
                )
        if abort_run:
            logger.info("[react] early exit requested by skill run_id=%s", run_id)
            merge_round_into_state(state, obs_list, gu, direct, refs)
            state.cancelled = True
            return
        merge_round_into_state(state, obs_list, gu, direct, refs)
        satisfied = await append_round_and_evaluate(
            ctx, state, resp, provider, progress_callback, round_num,
            run_id=run_id if run_id is not None else getattr(ctx, "run_id", None),
        )
        if satisfied:
            return
