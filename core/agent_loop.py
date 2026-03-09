"""
Agent Loop - Reusable tool-calling agent loop.

Used by deep-research sub-agent and shareable with main ReAct.
Round outcomes are explicit; LLM call, tool execution, and
summarize are separate single-purpose functions.
"""

import json
import logging
import re
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Any

from constants import (
    AGENT_LOOP_FORCE_TOOL_MSG,
    AGENT_LOOP_RESULTS_PREFIX,
    AGENT_LOOP_SUMMARIZE_GUIDANCE_PREFIX,
    EVAL_MIN_OBSERVATIONS,
    EVAL_OBSERVATIONS_TAIL,
    EVAL_OBSERVATION_PREVIEW_LEN,
    EVAL_SATISFIED_JSON_PATTERN,
    FOLLOW_UP_MSG,
    OBSERVATION_PREVIEW_LEN,
    SUMMARIZE_MSG,
)
from providers import BaseProvider

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


def parse_tool_calls(content: str) -> tuple[str | None, list[dict]]:
    """Extract direct reply or tool chain from LLM content.

    Args:
        content: Raw LLM response content.

    Returns:
        (direct_reply, tool_chain). direct_reply is text before a JSON array;
        tool_chain is non-empty when the content contains a JSON array of
        tool call objects with "name" and optional "arguments"/"tool".
    """
    content = (content or "").strip()
    if not content:
        return None, []
    idx = content.rfind("[")
    if idx >= 0:
        try:
            arr = json.loads(content[idx:])
            if isinstance(arr, list) and arr:
                chain = [
                    {
                        "name": item["name"],
                        "arguments": item.get("arguments", {}),
                        "tool": item.get("tool", "query"),
                    }
                    for item in arr
                    if isinstance(item, dict) and item.get("name")
                ]
                if chain:
                    return content[:idx].strip() or None, chain
        except json.JSONDecodeError:
            pass
    return content, []


async def evaluate_observations(
    question: str,
    observations: list[str],
    provider: BaseProvider,
) -> tuple[bool, int]:
    """Evaluate whether observations suffice to answer the question.

    Skipped when fewer than EVAL_MIN_OBSERVATIONS results exist (saves an
    LLM round-trip for simple single-tool questions).

    Args:
        question: Original user question.
        observations: List of tool result strings.
        provider: LLM provider for the eval call.

    Returns:
        (satisfied, tokens_used). satisfied is True if the eval model thinks
        the observations contain useful info to answer. Defaults to True on
        any error to avoid blocking the agent unnecessarily.
    """
    if len(observations) < EVAL_MIN_OBSERVATIONS:
        return False, 0
    tail = observations[-EVAL_OBSERVATIONS_TAIL:]
    obs_text = "\n\n".join(
        _format_obs_line(i, obs, EVAL_OBSERVATION_PREVIEW_LEN)
        for i, obs in enumerate(tail)
    )
    sys_prompt = (
        "You evaluate if tool results contain USEFUL info to answer the question. "
        "Reply with JSON only: {\"satisfied\": true/false}. "
        "Be lenient: if ANY relevant content exists, satisfied=true."
    )
    user_prompt = f"Question: {question}\n\nObservations:\n{obs_text}\n\nSuffice? JSON only."
    try:
        resp = await provider.chat(
            [{"role": "user", "content": user_prompt}],
            tools=None,
            system_prompt=sys_prompt,
        )
        content = (resp.get("content") or "").strip()
        tokens = (resp.get("usage") or {}).get("total_tokens", 0)
        m = re.search(EVAL_SATISFIED_JSON_PATTERN, content)
        satisfied = json.loads(m.group()).get("satisfied", True) if m else True
        return satisfied, tokens
    except Exception as e:
        logger.warning("evaluate_observations failed: %s", e)
        return True, 0


# ---------------------------------------------------------------------------
# Private helpers (call order: as used from public API and each other)
# ---------------------------------------------------------------------------


def _format_obs_line(index: int, obs: str, preview_len: int) -> str:
    """Format a single observation line with optional truncation."""
    truncated = f"{obs[:preview_len]}..." if len(obs) > preview_len else obs
    return f"Obs {index + 1}: {truncated}"


async def _call_llm_round(
    provider: BaseProvider,
    messages: list[dict],
    tools: list[dict],
    system_prompt: str,
) -> tuple[str, list[tuple[str, str, dict]], str | None, int]:
    """Run one LLM round and resolve tool calls.

    Returns:
        (content, calls, direct, tokens). calls is list of (name, action, arguments).
    """
    resp = await provider.chat(messages, tools=tools, system_prompt=system_prompt)
    tokens = _compute_tokens_from_usage(resp.get("usage", {}))
    content = resp.get("content", "")
    native_calls = resp.get("tool_calls", [])
    direct, parsed_chain = parse_tool_calls(content)
    parsed_chain = parsed_chain if tools else []
    calls = _resolve_tool_calls(native_calls, parsed_chain, tools)
    return content, calls, direct, tokens


def _decide_no_calls_action(
    content: str,
    direct: str | None,
    all_observations: list[str],
    required_in_observations: str | None,
) -> tuple[RoundOutcome, str | None]:
    """Decide next step when the LLM returns no tool calls.

    Returns:
        (action, answer_or_none). FORCE: append force-tool and continue;
        RETURN: early exit with direct answer; BREAK: exit loop to summarize.
    """
    if _should_force_tool(all_observations, required_in_observations):
        return RoundOutcome.FORCE, None
    if all_observations:
        return RoundOutcome.BREAK, None
    if direct or content:
        return RoundOutcome.RETURN, _extract_answer(direct or content)
    return RoundOutcome.BREAK, None


def _append_force_tool_round(
    messages: list[dict],
    content: str,
    all_observations: list[str],
    round_num: int,
    required: str,
) -> None:
    """Append assistant reply and force-tool user message; caller continues loop."""
    messages.append({"role": "assistant", "content": content})
    results = _build_results_content(all_observations)
    messages.append({"role": "user", "content": f"{results}\n\n{AGENT_LOOP_FORCE_TOOL_MSG}"})
    logger.info(
        "[agent_loop] round=%d no_tools but required_in_observations=%r not found -> force tool call",
        round_num, required,
    )


async def _run_round_with_calls(
    *,
    calls: list[tuple[str, str, dict]],
    content: str,
    messages: list[dict],
    all_observations: list[str],
    question: str,
    required_in_observations: str | None,
    provider: BaseProvider,
    execute_tool: ExecuteToolFn,
) -> tuple[bool, int, dict[str, Any] | None]:
    """Execute tool calls, append to messages and observations, evaluate.

    Returns:
        (satisfied, eval_tokens, round_gen_ui).
    """
    round_observations, round_gen_ui = await _execute_calls(calls, execute_tool)
    all_observations.extend(round_observations)
    results_content = _build_results_content(round_observations)

    messages.append({"role": "assistant", "content": content})
    satisfied, eval_tok = await evaluate_observations(question, all_observations, provider)

    if required_in_observations and not _has_required_in_observations(
        all_observations, required_in_observations
    ):
        satisfied = False
        logger.info(
            "[agent_loop] required_in_observations=%r not found -> continue",
            required_in_observations,
        )

    if satisfied:
        messages.append({"role": "user", "content": results_content})
    else:
        messages.append({"role": "user", "content": f"{results_content}\n\n{FOLLOW_UP_MSG}"})
    return satisfied, eval_tok, round_gen_ui


async def _run_summarize_step(
    provider: BaseProvider,
    messages: list[dict],
    system_prompt: str,
    summarize_guidance: str | None,
) -> tuple[str, int]:
    """Append summarize user message, call LLM, return (answer_text, tokens)."""
    summarize_msg = SUMMARIZE_MSG
    if summarize_guidance:
        summarize_msg += f"{AGENT_LOOP_SUMMARIZE_GUIDANCE_PREFIX}{summarize_guidance}"
    resp = await provider.chat(
        messages + [{"role": "user", "content": summarize_msg}],
        system_prompt=system_prompt,
    )
    answer = _extract_answer(resp.get("content") or "")
    tokens = _compute_tokens_from_usage(resp.get("usage") or {})
    return answer, tokens


def _compute_tokens_from_usage(usage: dict) -> int:
    """Extract total token count from provider usage dict."""
    return usage.get("total_tokens", 0) or (
        usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
    )


def _extract_answer(text: str) -> str:
    """Extract answer text; unwrap JSON {\"answer\": \"...\"} if present."""
    ans = (text or "").strip()
    if ans.startswith("{") and '"answer"' in ans:
        try:
            parsed = json.loads(ans)
            if isinstance(parsed.get("answer"), str):
                return parsed["answer"].strip()
        except json.JSONDecodeError:
            pass
    return ans


def _resolve_tool_calls(
    native_calls: list,
    parsed_chain: list[dict],
    tools: list[dict],
) -> list[tuple[str, str, dict]]:
    """Resolve native tool_calls or parsed chain into (name, action, arguments)."""
    if native_calls:
        return [_parse_tool_args(tc) for tc in native_calls]
    if tools and parsed_chain:
        return [
            (
                item.get("name", ""),
                item.get("tool", "list"),
                item.get("arguments", {}) or {},
            )
            for item in parsed_chain
        ]
    return []


def _parse_tool_args(tc: dict) -> tuple[str, str, dict]:
    """Extract (skill_name, action, arguments) from a native tool_call object."""
    fn = tc.get("function") or {}
    name = fn.get("name", "")
    try:
        args = json.loads(fn.get("arguments", "{}"))
    except json.JSONDecodeError:
        args = {}
    action = str(args.pop("tool", args.pop("action", "list"))).strip() or "list"
    arguments = args.get("arguments", args)
    if not isinstance(arguments, dict):
        arguments = {}
    return name, action, arguments


def _build_results_content(observations: list[str]) -> str:
    """Build Results section content for messages."""
    return AGENT_LOOP_RESULTS_PREFIX + "\n".join(observations)


async def _execute_calls(
    calls: list[tuple[str, str, dict]],
    execute_tool: ExecuteToolFn,
) -> tuple[list[str], dict | None]:
    """Run a list of (name, action, arguments) calls. Returns (observations, gen_ui)."""
    observations: list[str] = []
    gen_ui: dict | None = None
    for name, action, arguments in calls:
        if not name:
            continue
        result = await execute_tool(name, action, arguments)
        obs = json.dumps(result, ensure_ascii=False)[:OBSERVATION_PREVIEW_LEN]
        if result.get("gen_ui"):
            gen_ui = result["gen_ui"]
        observations.append(f"[{name}.{action}]: {obs}")
    return observations, gen_ui


def _has_required_in_observations(observations: list[str], required: str) -> bool:
    """Return True if required substring appears in combined observations."""
    return required in " ".join(observations)


def _should_force_tool(
    all_observations: list[str],
    required_in_observations: str | None,
) -> bool:
    """Return True if we have observations but required substring is missing."""
    return bool(
        required_in_observations
        and all_observations
        and not _has_required_in_observations(all_observations, required_in_observations)
    )
