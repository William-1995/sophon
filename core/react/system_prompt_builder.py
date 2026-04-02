"""
ReAct System Prompt - Build system prompt for ReAct loop.

Injects user language detection and response context.
"""

import json
import re

from . import prompt_fragments as pf


def _build_user_response_context(question: str) -> dict:
    """Infer user's language and attach static tone/format hints for the reply."""
    q = (question or "").strip()
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", q))
    detected_lang = "zh" if has_cjk else "en"
    return {
        "language": detected_lang,
        "tone": pf.USER_CONTEXT_TONE,
        "format": pf.USER_CONTEXT_FORMAT,
    }


def _system_prompt_with_tools(
    current_time: str,
    composite: dict | None,
    user_response_context: dict,
    composite_body_max: int,
    multi_part: bool = False,
) -> str:
    """Build base system prompt when tools are available."""
    base = f"{pf.BASE_ASSISTANT_WITH_TOOLS}{pf.EXEC_DISCIPLINE}"
    if multi_part:
        base += pf.MULTIPART_STRICT
    else:
        base += pf.DECOMPOSE_SUBTASKS
    base += f" Current time: {current_time}"
    if composite:
        body = composite.get("body", "")
        if body:
            trimmed = body[:composite_body_max]
            if len(body) > composite_body_max:
                trimmed += "\n...[truncated]"
            base += f"\n\nTask guidance:\n{trimmed}"
    return f"{base}\n\nResponse context (follow strictly): {json.dumps(user_response_context)}"


def _system_prompt_without_tools(
    current_time: str,
    user_response_context: dict,
) -> str:
    """Build base system prompt when no tools are available."""
    ctx_block = f"\n\nResponse context (follow strictly): {json.dumps(user_response_context)}"
    return (
        f"{pf.BASE_ASSISTANT_WITHOUT_TOOLS}"
        f"Current time: {current_time}"
        f"{ctx_block}"
    )


def build_system_prompt(
    tools: list,
    composite: dict | None,
    current_time: str,
    override: str | None,
    question: str,
    composite_body_max: int = 12000,
    multi_part: bool = False,
) -> str:
    """Build system prompt for the ReAct loop.

    Injects user_response_context object so LLM replies in the user's language.

    Args:
        tools: List of available tools.
        composite: Optional composite skill definition.
        current_time: Current timestamp.
        override: Optional system prompt override.
        question: User question for language detection.
        composite_body_max: Max chars for composite body injection.
        multi_part: When True, add stricter multi-part handling rules.

    Returns:
        Complete system prompt string.
    """
    user_response_context = _build_user_response_context(question)
    default = (
        _system_prompt_with_tools(
            current_time, composite, user_response_context, composite_body_max,
            multi_part=multi_part,
        )
        if tools
        else _system_prompt_without_tools(current_time, user_response_context)
    )
    return f"{override.strip()}\n\n{default}" if (override and override.strip()) else default
