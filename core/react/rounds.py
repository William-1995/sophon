"""
ReAct Rounds - Round loop and LLM invocation.

Handles per-round LLM calls, cancellation checks, and tool execution.
"""

import logging
from typing import Any

from config import get_config
from constants import DEFAULT_MAX_ROUNDS
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
        round_num,
        len(ctx.tools),
        [t.get("function", {}).get("name") for t in ctx.tools],
    )
    try:
        resp = await provider.chat(
            ctx.messages, tools=ctx.tools, system_prompt=ctx.system
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
            {"tokens": tok},
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
