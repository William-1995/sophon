"""
Agent Loop - Reusable tool-calling agent loop.

Used by deep-research sub-agent and shareable with main ReAct.
"""

import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from constants import (
    EVAL_OBSERVATIONS_TAIL,
    EVAL_OBSERVATION_PREVIEW_LEN,
    FOLLOW_UP_MSG,
    OBSERVATION_PREVIEW_LEN,
    SUMMARIZE_MSG,
)
from core.providers import BaseProvider

logger = logging.getLogger(__name__)


def parse_tool_calls(content: str) -> tuple[str | None, list[dict]]:
    """Extract direct reply or tool chain from LLM content.

    Returns (direct_reply, tool_chain). tool_chain is non-empty when the
    content contains a JSON array of tool call objects.
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


def _format_obs_line(index: int, obs: str, preview_len: int) -> str:
    truncated = f"{obs[:preview_len]}..." if len(obs) > preview_len else obs
    return f"Obs {index + 1}: {truncated}"


# Only evaluate when there are enough observations to justify an LLM call.
# A single result rarely needs evaluation — the follow-up round handles it.
_EVAL_MIN_OBSERVATIONS = 2


async def evaluate_observations(
    question: str,
    observations: list[str],
    provider: BaseProvider,
) -> tuple[bool, int]:
    """Lightweight eval: do observations suffice to answer?

    Skipped when fewer than _EVAL_MIN_OBSERVATIONS results exist (saves an
    LLM round-trip for simple single-tool questions).
    Returns (satisfied, tokens_used). Defaults to satisfied=True on any error
    to avoid blocking the agent unnecessarily.
    """
    if len(observations) < _EVAL_MIN_OBSERVATIONS:
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
        m = re.search(r'\{[^{}]*"satisfied"[^{}]*\}', content)
        satisfied = json.loads(m.group()).get("satisfied", True) if m else True
        return satisfied, tokens
    except Exception as e:
        logger.warning("evaluate_observations failed: %s", e)
        return True, 0


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


ExecuteToolFn = Callable[[str, str, dict], Awaitable[dict[str, Any]]]


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


async def run_tool_agent(
    question: str,
    provider: BaseProvider,
    tools: list[dict],
    system_prompt: str,
    max_rounds: int,
    execute_tool: ExecuteToolFn,
    summarize_guidance: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Run tool-calling agent loop (skills only, no MCP).

    execute_tool(skill_name, action, arguments) -> result dict.
    Returns (answer_text, metadata).
    """
    messages: list[dict] = [{"role": "user", "content": question}]
    total_tokens = 0
    all_observations: list[str] = []
    gen_ui_collected: dict[str, Any] | None = None

    for round_num in range(1, max_rounds + 1):
        try:
            resp = await provider.chat(messages, tools=tools, system_prompt=system_prompt)
        except Exception as e:
            logger.warning("agent_loop llm_call failed round=%s: %s", round_num, e)
            raise

        usage = resp.get("usage", {})
        total_tokens += usage.get("total_tokens", 0) or (
            usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        )

        content = resp.get("content", "")
        native_calls = resp.get("tool_calls", [])
        direct, parsed_chain = parse_tool_calls(content)
        effective_chain = parsed_chain if tools else []

        if not native_calls and not effective_chain:
            if all_observations:
                logger.info("agent_loop round=%s: no tools, have observations -> summarize", round_num)
                break
            if direct or content:
                return _extract_answer(direct or content), {"tokens": total_tokens, "gen_ui": gen_ui_collected}
            break

        calls: list[tuple[str, str, dict]] = (
            [_parse_tool_args(tc) for tc in native_calls]
            if native_calls
            else [(item.get("name", ""), item.get("tool", "list"), item.get("arguments", {}) or {})
                  for item in effective_chain]
        )

        round_observations, round_gen_ui = await _execute_calls(calls, execute_tool)
        all_observations.extend(round_observations)
        if round_gen_ui:
            gen_ui_collected = round_gen_ui

        messages.append({"role": "assistant", "content": content})
        results_content = "Results:\n" + "\n".join(round_observations)
        satisfied, eval_tok = await evaluate_observations(question, all_observations, provider)
        total_tokens += eval_tok

        if satisfied:
            logger.info("agent_loop round=%s: evaluation satisfied -> summarize", round_num)
            messages.append({"role": "user", "content": results_content})
            break
        messages.append({"role": "user", "content": f"{results_content}\n\n{FOLLOW_UP_MSG}"})

    summarize_msg = SUMMARIZE_MSG
    if summarize_guidance:
        summarize_msg += f"\n\nUse this interpretation guidance:\n{summarize_guidance}"
    try:
        final_resp = await provider.chat(
            messages + [{"role": "user", "content": summarize_msg}],
            system_prompt=system_prompt,
        )
    except Exception as e:
        logger.warning("agent_loop summarize failed: %s", e)
        raise

    final_content = _extract_answer(final_resp.get("content") or "")
    total_tokens += (final_resp.get("usage") or {}).get("total_tokens", 0)
    return final_content, {"tokens": total_tokens, "gen_ui": gen_ui_collected}
