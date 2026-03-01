"""
Tool Builder - Build OpenAI-format tool definitions from skills.

Reusable for main ReAct agent and sub-agents.
"""

from typing import Any

from constants import (
    TOOL_ACTION_HINT_MAX,
    TOOL_FALLBACK_SECTION_MAX,
    TOOL_ORCHESTRATION_SECTION_MAX,
    TOOL_TOOLS_SECTION_MAX,
    TOOL_WORKSPACE_SECTION_MAX,
)

_DEFAULT_TOOL_DESC = "Action name as defined in the skill's Tools section."


def build_tools_from_skills(
    skills: list[dict[str, Any]],
    loader: Any,
) -> list[dict]:
    """Build OpenAI-format tool definitions for a list of skills.

    Skills without scripts (e.g. chat-only) are skipped.
    Compatible with an empty input list.
    """
    tools: list[dict] = []
    for s in skills:
        name = s.get("skill_name", "")
        if not name:
            continue
        full = loader.get_skill(name)
        if not (full and full.get("scripts")):
            continue
        desc = _enrich_description(s.get("skill_description", ""), full.get("body", ""))
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": desc,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tool": {
                            "type": "string",
                            "description": _action_hint(full),
                        },
                        "arguments": {
                            "type": "object",
                            "description": "Tool-specific args as defined in the Tools section.",
                        },
                    },
                },
            },
        })
    return tools


def _extract_section(body: str, heading: str, max_chars: int) -> str | None:
    """Extract content of a ## heading section, truncated to max_chars."""
    marker = f"## {heading}"
    if marker not in body:
        return None
    after = body.split(marker, 1)[1]
    section = after.split("##")[0].strip()
    return section[:max_chars] if section else None


def _enrich_description(base_desc: str, body: str) -> str:
    """Enrich skill description with key SKILL.md sections."""
    if not body:
        return base_desc

    sections: list[str] = []
    for heading, label, limit in (
        ("Workspace",            "Workspace rules",  TOOL_WORKSPACE_SECTION_MAX),
        ("Orchestration Guidance", "When to use",    TOOL_ORCHESTRATION_SECTION_MAX),
        ("Tools",                "Tools",            TOOL_TOOLS_SECTION_MAX),
    ):
        text = _extract_section(body, heading, limit)
        if text:
            sections.append(f"{label}:\n{text}")

    if not sections and "## " in body:
        fallback = body.split("## ", 1)[1].split("##")[0].strip()
        if fallback:
            sections.append(fallback[:TOOL_FALLBACK_SECTION_MAX])

    return f"{base_desc}\n\n" + "\n\n".join(sections) if sections else base_desc


def _action_hint(skill_data: dict) -> str:
    """Extract available action names from ## Tools section."""
    body = skill_data.get("body") or ""
    tools_section = _extract_section(body, "Tools", max_chars=len(body))
    if not tools_section:
        return _DEFAULT_TOOL_DESC

    actions = [
        line.lstrip("#").strip().split()[0]
        for line in tools_section.split("\n")
        if line.strip().startswith("### ") and line.strip().split()
    ]
    if not actions:
        return _DEFAULT_TOOL_DESC

    hint = ", ".join(actions)[:TOOL_ACTION_HINT_MAX]
    return f"Action from Tools: {hint}"
