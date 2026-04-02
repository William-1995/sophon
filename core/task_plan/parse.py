"""
Parse LLM output into normalized todo items for task_plan.
"""

from __future__ import annotations

import json
from typing import Any


def try_parse_todos_from_llm_content(content: str) -> list[dict] | None:
    """Extract todo list from LLM response. Expects JSON array or object with items/todos."""
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


def normalize_todo_items(raw: list[Any]) -> list[dict[str, Any]]:
    """Ensure each todo has id, title, status (pending|in_progress|done)."""
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


def parse_planner_response(content: str) -> dict[str, Any] | None:
    """Parse the planner LLM output into either clarify or plan mode."""
    content = (content or "").strip()
    if "```" in content:
        for part in content.split("```"):
            if ("mode" in part or "items" in part) and "{" in part:
                content = part.replace("json", "").strip()
                break
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    mode = str(data.get("mode") or "").strip().lower()
    if mode == "clarify":
        return {
            "mode": "clarify",
            "message": str(data.get("message") or "").strip(),
            "missing_inputs": [
                str(item).strip()
                for item in (data.get("missing_inputs") or [])
                if str(item).strip()
            ],
        }
    if mode == "plan" or isinstance(data.get("items"), list) or isinstance(data.get("todos"), list):
        items = data.get("items") if isinstance(data.get("items"), list) else data.get("todos")
        return {"mode": "plan", "items": items}
    return None
