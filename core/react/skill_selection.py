"""
ReAct Skill Selection - Round 1 skill picker.

Lightweight LLM call to select which skills to load for a question.
"""

import json
import logging
from typing import Any

from providers import BaseProvider

logger = logging.getLogger(__name__)


def _try_parse_json(content: str) -> dict | None:
    """Try to parse JSON from content, with a fallback substring search.

    Args:
        content: Text that may contain JSON.

    Returns:
        Parsed dict or None if parsing fails.
    """
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    idx = content.find('"skills"')
    if idx >= 0:
        brace_start = content.rfind("{", 0, idx)
        brace_end = content.find("}", idx)
        if brace_start >= 0 and brace_end >= 0:
            try:
                return json.loads(content[brace_start : brace_end + 1])
            except json.JSONDecodeError:
                pass
    return None


async def select_skills_for_question(
    question: str,
    provider: BaseProvider,
    skills_brief: list[dict[str, str]],
) -> tuple[list[str], int, bool]:
    """Round 1: lightweight LLM call to pick which skill(s) to load and whether multi-step planning is needed.

    Args:
        question: User question to analyze.
        provider: LLM provider for selection inference.
        skills_brief: List of available skills with names and descriptions.

    Returns:
        Tuple of (selected_skill_names, tokens_used, multi_step).
        - multi_step: True when the request has multiple distinct sub-tasks that benefit from todos.plan
          (e.g. 'search X and write to file Y'). False for single coherent questions even with 'and'
          (e.g. 'What is Python and how to install it' = one research task).
    """
    if not skills_brief:
        return [], 0, False
    skill_list = "\n".join(
        f"- {s['skill_name']}: {s['skill_description'][:180]}..." for s in skills_brief
    )
    sys_prompt = (
        "Pick ALL skills needed to fully answer every part of the question. "
        'Reply with JSON only: {"skills": ["skill_name1"], "multi_step": true|false}. '
        "Use exact skill_name from the list. For compound questions, select multiple skills. "
        "multi_step: true when the request has multiple distinct sub-tasks that should be planned separately "
        "(e.g. 'search for X and summarize', 'do A, B, and C'). "
        "multi_step: false for single coherent questions (e.g. 'What is X and why', 'What is Python and how to install it')."
    )
    user_prompt = f"Question: {question}\n\nAvailable skills:\n{skill_list}\n\nWhich skill(s) and multi_step? JSON only."
    tokens = 0
    try:
        resp = await provider.chat(
            [{"role": "user", "content": user_prompt}],
            tools=None,
            system_prompt=sys_prompt,
        )
        usage = resp.get("usage") or {}
        tokens = usage.get("total_tokens", 0) or (
            usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        )
        content = (resp.get("content") or "").strip()
        if "```" in content:
            for part in content.split("```"):
                if "skills" in part and "{" in part:
                    content = part.replace("json", "").strip()
                    break
        data = _try_parse_json(content)
        if data and isinstance(data.get("skills"), list):
            valid = {s["skill_name"] for s in skills_brief}
            selected = [x for x in data["skills"] if isinstance(x, str) and x in valid]
            multi_step = bool(data.get("multi_step"))
            if selected:
                logger.info("[react] selected_skills=%s multi_step=%s tokens=%d", selected, multi_step, tokens)
                return selected, tokens, multi_step
            return selected, tokens, multi_step
    except Exception as e:
        logger.warning("[react] _select_skills_for_question failed: %s", e)
    logger.info("[react] selected_skills=[] (none matched) tokens=%d", tokens)
    return [], tokens, False
