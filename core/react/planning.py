"""
ReAct Planning - Plan-first phase for todos capability.

Produces a todo list before execution. Emits TODOS_PLAN; execution can update via update_todos tool.
"""

import json
import logging
from typing import Any

from providers import BaseProvider

logger = logging.getLogger(__name__)


def _try_parse_todos(content: str) -> list[dict] | None:
    """Extract todos from LLM response. Expects JSON array or object with 'items' key."""
    content = (content or "").strip()
    if "```" in content:
        for part in content.split("```"):
            if ("items" in part or "[{" in part) and "{" in part:
                content = part.replace("json", "").strip()
                break
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data["items"]
        if isinstance(data, dict) and isinstance(data.get("todos"), list):
            return data["todos"]
        return None
    except json.JSONDecodeError:
        idx = content.find("[")
        if idx >= 0:
            end = content.rfind("]") + 1
            if end > idx:
                try:
                    return json.loads(content[idx:end])
                except json.JSONDecodeError:
                    pass
    return None


def _normalize_todos(raw: list) -> list[dict[str, Any]]:
    """Ensure each todo has id, title, status."""
    out: list[dict[str, Any]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id") or i + 1)
        title = str(item.get("title") or item.get("task") or item.get("name") or "").strip()
        if not title:
            continue
        status = str(item.get("status") or "pending").lower()
        if status not in ("pending", "in_progress", "done"):
            status = "pending"
        out.append({"id": tid, "title": title, "status": status})
    return out


async def run_planning_phase(
    question: str,
    tools_brief: list[dict],
    provider: BaseProvider,
) -> list[dict[str, Any]]:
    """Run lightweight LLM call to produce a todo plan.

    Args:
        question: User question.
        tools_brief: Short descriptions of available tools (for context).
        provider: LLM provider.

    Returns:
        List of todo dicts: [{id, title, status}, ...]. Empty list on failure.
    """
    tools_text = "\n".join(
        f"- {(t.get('function') or {}).get('name', t.get('name', '?'))}: {((t.get('function') or {}).get('description') or t.get('description', ''))[:100]}"
        for t in (tools_brief or [])[:30]
    )
    sys_prompt = (
        "You are a task planner. Given the user's question and available tools, "
        "produce a brief todo list as JSON. Reply with JSON only. "
        'Format: {"items": [{"id": "1", "title": "...", "status": "pending"}, ...]}. '
        "Keep 2-8 items. Use clear, actionable titles. All start as status: pending."
    )
    user_prompt = f"Question: {question}\n\nAvailable tools:\n{tools_text}\n\nTodo plan (JSON only):"
    try:
        resp = await provider.chat(
            [{"role": "user", "content": user_prompt}],
            tools=None,
            system_prompt=sys_prompt,
        )
        content = (resp.get("content") or "").strip()
        raw = _try_parse_todos(content)
        if raw:
            todos = _normalize_todos(raw)
            if todos:
                logger.info("[planning] todos_count=%d", len(todos))
                return todos
    except Exception as e:
        logger.warning("[planning] failed: %s", e)
    return []
