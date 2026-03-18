"""
ReAct Main - Core ReAct loop orchestration.

Coordinates the main ReAct execution flow: preparation, rounds, and finalization.
"""

import logging
from pathlib import Path
from typing import Any

from providers import BaseProvider
from core.react.context import ImmutableRunContext, MutableRunState
from core.react.preparation import prepare_react_run
from core.react.rounds import run_react_rounds
from core.react.utils import dedupe_references, emit_progress
from core.react.finalization import finalize_react_answer

logger = logging.getLogger(__name__)


# Re-export for external use
from core.react.tool_parsing import (  # noqa: E402
    get_round_action,
    parse_native_tool_call,
    parse_single_tool_call,
    process_llm_response,
    resolve_call_items,
)


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
