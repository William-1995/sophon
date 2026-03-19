"""
ReAct Finalization - Answer generation and result processing.

Handles final summarization, answer extraction, and reference deduplication.
"""

import logging
from typing import Any

from constants import SUMMARIZE_MSG
from core.agent_loop import evaluate_observations
from core.react.context import ImmutableRunContext, MutableRunState
from core.react.utils import (
    emit_progress,
    extract_direct_answer,
    truncate_observations_for_llm,
)
from providers import BaseProvider

logger = logging.getLogger(__name__)


async def summarize_and_extract_answer(
    messages: list[dict],
    system: str,
    provider: BaseProvider,
    db: Any,
    session_id: str,
    multi_part: bool = False,
    run_id: str | None = None,
) -> tuple[str, int]:
    """Run final summarize LLM call.

    Args:
        messages: Conversation messages.
        system: System prompt.
        provider: LLM provider.
        db: Database path.
        session_id: Session identifier.
        multi_part: When True, add synthesis guidance to avoid echoing one part only.

    Returns:
        Tuple of (final_answer, tokens_used).
    """
    summarize_prompt = SUMMARIZE_MSG
    if multi_part:
        summarize_prompt += (
            " The user asked multiple things; address EACH part. "
            "Do NOT output only one tool's result verbatim. Synthesize a concise answer covering all parts."
        )
    try:
        resp = await provider.chat(
            messages + [{"role": "user", "content": summarize_prompt}],
            system_prompt=system,
        )
    except Exception as e:
        if db.exists():
            from db.logs import insert as log_insert
            log_insert(db, "ERROR", f"llm_summarize_failed: {e}", session_id, {"error": str(e)})
        raise

    content = (resp.get("content") or "").strip()
    answer = extract_direct_answer(content)
    tokens = (resp.get("usage") or {}).get("total_tokens", 0)
    if tokens > 0 and db.exists():
        from db.logs import insert as log_insert
        from db.metrics import insert as metrics_insert
        log_insert(
            db, "INFO", f"tokens step=summarize tokens={tokens}",
            session_id, {"step": "summarize", "tokens": tokens},
        )
        metrics_insert(db, "llm_tokens", float(tokens), tags={"step": "summarize", "session_id": session_id, "run_id": run_id or ""})
    return answer, tokens


async def finalize_react_answer(
    ctx: ImmutableRunContext,
    state: MutableRunState,
    provider: BaseProvider,
    run_id: str | None = None,
) -> tuple[str, int]:
    """Run summarize step if no direct answer from skill.

    Args:
        ctx: Immutable run context.
        state: Mutable run state.
        provider: LLM provider.

    Returns:
        Tuple of (final_answer, total_tokens).
    """
    if state.answer_from_skill:
        return state.answer_from_skill, state.total_tokens
    rid = run_id if run_id is not None else getattr(ctx, "run_id", None)
    final_answer, sum_tokens = await summarize_and_extract_answer(
        ctx.messages, ctx.system, provider, ctx.db, ctx.session_id,
        multi_part=ctx.multi_part,
        run_id=rid,
    )
    return final_answer, state.total_tokens + sum_tokens


async def append_round_and_evaluate(
    ctx: ImmutableRunContext,
    state: MutableRunState,
    resp: dict,
    provider: BaseProvider,
    progress_callback: Any,
    round_num: int,
    run_id: str | None = None,
) -> bool:
    """Append assistant + user message, run evaluation, emit progress.

    Args:
        ctx: Immutable run context.
        state: Mutable run state.
        resp: LLM response dict.
        provider: LLM provider.
        progress_callback: Optional progress callback.
        round_num: Current round number.

    Returns:
        True if evaluation is satisfied (should stop).
    """
    content = resp.get("content", "")
    ctx.messages.append({"role": "assistant", "content": content})
    results_content = truncate_observations_for_llm(state.observations)
    satisfied, eval_tok = await evaluate_observations(
        ctx.question, state.observations, provider, multi_part=ctx.multi_part
    )
    state.total_tokens += eval_tok
    if eval_tok > 0 and ctx.db.exists():
        from db.logs import insert as log_insert
        from db.metrics import insert as metrics_insert
        log_insert(
            ctx.db,
            "INFO",
            f"tokens step=evaluate tokens={eval_tok}",
            ctx.session_id,
            {"step": "evaluate", "tokens": eval_tok, "round": round_num},
        )
        metrics_insert(
            ctx.db,
            "llm_tokens",
            float(eval_tok),
            tags={"step": "evaluate", "round": round_num, "session_id": ctx.session_id, "run_id": run_id or ""},
        )
    emit_progress(progress_callback, state.total_tokens, round_num)

    from constants import FOLLOW_UP_MSG
    next_content = (
        results_content if satisfied else f"{results_content}\n\n{FOLLOW_UP_MSG}"
    )
    ctx.messages.append({"role": "user", "content": next_content})
    if satisfied:
        logger.info("round=%d: evaluation satisfied -> summarize", round_num)
    return satisfied
