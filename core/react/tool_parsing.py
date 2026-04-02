"""
ReAct Tool Parsing - Parse LLM tool calls into standardized format.

Handles native tool_calls and chain-of-thought parsed tool invocations.
"""

import json
import logging

from core.agent_loop_helpers import parse_tool_calls
from core.react.utils import extract_direct_answer

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
    content = resp.get("content", "")
    tool_calls = resp.get("tool_calls", [])
    logger.debug(
        "round=%d tool_calls=%d content_len=%d",
        round_num, len(tool_calls), len(content or ""),
    )

    call_items = resolve_call_items(resp, tools, round_num)
    if call_items is None:
        if observations:
            logger.info("round=%d: no tools, have observations -> summarize", round_num)
        direct, _ = parse_tool_calls(content)
        raw = (direct or content) or ""
        ans = extract_direct_answer(raw)
        if tools:
            # Tools are available: do not treat plain prose as a final answer (avoids
            # "I will read the file..." exiting the loop with no tool_calls).
            text = (content or "").strip()
            if text.startswith("{") and '"answer"' in text:
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed.get("answer"), str):
                        extracted = parsed["answer"].strip()
                        if extracted:
                            return (None, extracted)
                except json.JSONDecodeError:
                    pass
            return (None, None)
        return (None, ans) if ans else (None, None)

    parsed = [
        parse_single_tool_call(n, t, i, from_native_tool_calls=bool(tool_calls))
        for n, t, i in call_items
    ]
    calls = [x for x in parsed if x is not None]
    for name, tool, arguments, display_summary in calls:
        logger.debug(
            "tool_call: skill=%s tool=%s arguments=%s display_summary=%s",
            name, tool, arguments, display_summary,
        )
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
    if calls:
        calls_desc = [(c[0], c[1]) for c in calls]
        logger.debug("[react] round=%d executing %s", round_num, calls_desc)
    if direct_answer:
        return ("direct", direct_answer, None)
    if calls is None:
        return ("break", None, None)
    return ("run_tools", None, calls)
