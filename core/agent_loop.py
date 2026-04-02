"""
Agent Loop - Reusable tool-calling agent loop.

Used by deep-research sub-agent and shareable with main ReAct.
Round outcomes are explicit; LLM call, tool execution, and
summarize are separate single-purpose functions.
"""

import logging
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Any
from providers import BaseProvider

from core.agent_loop_helpers import (
    RoundOutcome,
    _append_force_tool_round,
    _call_llm_round,
    _decide_no_calls_action,
    _run_round_with_calls,
    _run_summarize_step
)

logger = logging.getLogger(__name__)

ExecuteToolFn = Callable[[str, str, dict], Awaitable[dict[str, Any]]]


class RoundOutcome(Enum):
    """Outcome when the LLM returns no tool calls in a round."""

    FORCE = "force"  # Append force-tool message and continue loop.
    RETURN = "return"  # Early exit with direct answer.
    BREAK = "break"  # Exit loop to run summarize step.


# ---------------------------------------------------------------------------
# Public API (call order: entry point first, then helpers used by flow)
# ---------------------------------------------------------------------------


async def run_tool_agent(
    question: str,
    provider: BaseProvider,
    tools: list[dict],
    system_prompt: str,
    max_rounds: int,
    execute_tool: ExecuteToolFn,
    summarize_guidance: str | None = None,
    required_in_observations: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Run tool-calling agent loop (skills only, no MCP).

    Args:
        question: User question to answer.
        provider: LLM provider for chat and tool-calling.
        tools: Tool definitions passed to the provider.
        system_prompt: System prompt for the agent.
        max_rounds: Maximum number of tool-calling rounds.
        execute_tool: Async (skill_name, action, arguments) -> result dict.
        summarize_guidance: Optional extra guidance for the final summarize step.
        required_in_observations: Optional substring that must appear in observations.

    Returns:
        (answer_text, metadata) where metadata has "tokens" and "gen_ui".
    """
    logger.info("[agent_loop] start max_rounds=%d", max_rounds)
    messages: list[dict] = [{"role": "user", "content": question}]
    total_tokens = 0
    all_observations: list[str] = []
    gen_ui_collected: dict[str, Any] | None = None

    for round_num in range(1, max_rounds + 1):
        try:
            content, calls, direct, round_tokens = await _call_llm_round(
                provider, messages, tools, system_prompt
            )
        except Exception as e:
            logger.warning("[agent_loop] round=%d llm_call_failed: %s", round_num, e)
            raise
        total_tokens += round_tokens

        if not calls:
            action, answer = _decide_no_calls_action(
                content, direct, all_observations, required_in_observations
            )
            if action == RoundOutcome.FORCE:
                _append_force_tool_round(
                    messages, content, all_observations, round_num, required_in_observations
                )
                continue
            if action == RoundOutcome.RETURN:
                return answer or "", {"tokens": total_tokens, "gen_ui": gen_ui_collected}
            logger.info("[agent_loop] round=%d no_tools have_observations -> summarize", round_num)
            break

        logger.info(
            "[agent_loop] round=%d tool_calls=%d tools=%s",
            round_num, len(calls), [(c[0], c[1]) for c in calls],
        )
        satisfied, eval_tok, round_gen_ui = await _run_round_with_calls(
            calls=calls,
            content=content,
            messages=messages,
            all_observations=all_observations,
            question=question,
            required_in_observations=required_in_observations,
            provider=provider,
            execute_tool=execute_tool,
        )
        total_tokens += eval_tok
        if round_gen_ui:
            gen_ui_collected = round_gen_ui

        if satisfied:
            logger.info("[agent_loop] round=%d satisfied -> summarize", round_num)
            break

    try:
        final_content, sum_tokens = await _run_summarize_step(
            provider, messages, system_prompt, summarize_guidance
        )
    except Exception as e:
        logger.warning("[agent_loop] summarize_failed: %s", e)
        raise
    total_tokens += sum_tokens
    logger.info("[agent_loop] done answer_len=%d tokens=%d", len(final_content or ""), total_tokens)
    return final_content, {"tokens": total_tokens, "gen_ui": gen_ui_collected}