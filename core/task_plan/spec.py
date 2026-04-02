"""
Task plan (built-in ReAct tool) — identifiers and OpenAI tool schema.

Not a filesystem skill: orchestration registers this tool when `task_plan` is exposed
in config and selected for the session.
"""

from __future__ import annotations

from typing import Any

from constants import TASK_PLAN_TOOL_DESCRIPTION_TRUNCATE

# OpenAI function name (same shape as skill-backed tools: tool + arguments + display_summary)
TASK_PLAN_SKILL_NAME = "task_plan"
TASK_PLAN_ENTRY_ACTION = "plan"

TASK_PLAN_DESCRIPTION = (
    "Plan a multi-step task as a short todo list and ask the user to confirm before execution. "
    "Use when human review of the plan is appropriate. "
    "After confirmation, continue with other tools (search, filesystem, etc.); this tool does not execute the steps."
)

REACT_BUILTIN_SKILL_NAMES: frozenset[str] = frozenset({TASK_PLAN_SKILL_NAME})


def builtin_skill_brief(skill_name: str) -> dict[str, str] | None:
    """Return picker/capabilities brief for a built-in tool name, or None."""
    if skill_name == TASK_PLAN_SKILL_NAME:
        return {
            "skill_name": TASK_PLAN_SKILL_NAME,
            "skill_description": TASK_PLAN_DESCRIPTION,
        }
    return None


def openai_tools_to_brief(tools: list[Any] | None) -> list[dict[str, str]]:
    """Flatten OpenAI tool list to [{name, description}, ...] for planner context."""
    out: list[dict[str, str]] = []
    for t in tools or []:
        fn = t.get("function") if isinstance(t, dict) else None
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name", "") or "")
        desc = str(fn.get("description") or "")[:TASK_PLAN_TOOL_DESCRIPTION_TRUNCATE]
        if name:
            out.append({"name": name, "description": desc})
    return out


def build_task_plan_openai_tool() -> dict[str, Any]:
    """Single OpenAI-format tool definition (mirrors skill tools: tool + arguments + display_summary)."""
    return {
        "type": "function",
        "function": {
            "name": TASK_PLAN_SKILL_NAME,
            "description": TASK_PLAN_DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {
                    "tool": {
                        "type": "string",
                        "description": 'Action name. Must be "plan".',
                        "enum": [TASK_PLAN_ENTRY_ACTION],
                    },
                    "arguments": {
                        "type": "object",
                        "description": "For plan: { question: string } — summarize the user task to plan.",
                    },
                    "display_summary": {
                        "type": "string",
                        "description": (
                            "REQUIRED. One short sentence for the user (e.g. 'Drafting a step-by-step plan for your approval')."
                        ),
                    },
                },
                "required": ["tool", "arguments", "display_summary"],
            },
        },
    }
