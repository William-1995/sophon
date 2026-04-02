"""Planner LLM prompts — isolated from runner I/O."""

from constants import TASK_PLAN_TOOLS_BRIEF_MAX_ITEMS

SYSTEM_PROMPT = (
    "You are a task planner. First assess whether the request is ready to plan. "
    "If key inputs are missing, return a brief clarification request instead of a plan. "
    "If the request is ready, produce a brief todo list as JSON using only tools from the Available tools list. "
    'Format: {"items": [{"id": "1", "title": "...", "status": "pending"}, ...]}. '
    "Keep 2-8 items. Use clear, actionable titles. All start as status: pending. "
    "When the task contains a collection (for example URLs, rows, files, or records), keep the batch intact in the plan and do not shrink it to a single representative sample. If one item fails, continue with the rest and list failures separately in the plan."
)


def format_tools_brief(tools_brief: list[dict[str, str]] | None) -> str:
    """Render tools_brief for the user message."""
    if not tools_brief:
        return ""
    lines: list[str] = []
    for t in tools_brief[:TASK_PLAN_TOOLS_BRIEF_MAX_ITEMS]:
        name = t.get("name", "")
        desc = (t.get("description") or "").strip()
        if name:
            lines.append(f"- {name}: {desc}" if desc else f"- {name}")
    return "\n".join(lines) if lines else ""


def build_user_prompt(question: str, tools_text: str) -> str:
    if tools_text:
        return (
            f"Task: {question}\n\nAvailable tools:\n{tools_text}\n\n"
            "First decide whether enough information exists to plan. "
            "If the task refers to multiple URLs, rows, files, or records, treat it as batch work and keep the whole collection in scope. "
            "Do not plan only the first item as a sample. If one item fails or is unavailable, continue with the remaining items and record the failure instead of stopping. "
            'Return JSON only with one of two shapes:\n'
            '1) {"mode": "clarify", "message": "...", "missing_inputs": ["..."]}\n'
            '2) {"mode": "plan", "items": [{"id": "1", "title": "...", "status": "pending"}, ...]}\n'
        )
    return (
        f"Task: {question}\n\n"
        "First decide whether enough information exists to plan. "
        "If the task refers to multiple URLs, rows, files, or records, treat it as batch work and keep the whole collection in scope. "
        "Do not plan only the first item as a sample. If one item fails or is unavailable, continue with the remaining items and record the failure instead of stopping. "
        'Return JSON only with one of two shapes:\n'
        '1) {"mode": "clarify", "message": "...", "missing_inputs": ["..."]}\n'
        '2) {"mode": "plan", "items": [{"id": "1", "title": "...", "status": "pending"}, ...]}\n'
    )
