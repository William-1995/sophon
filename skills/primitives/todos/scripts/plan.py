#!/usr/bin/env python3
"""
Todos plan - Produce todo list for complex tasks, request user confirmation (HITL).

Two-phase: (1) produce plan + __decision_request, (2) on confirm return success.
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

_project_root = Path(os.environ.get("SOPHON_ROOT", Path(__file__).resolve().parent.parent.parent.parent.parent))
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from config import get_config
from core.ipc import emit_event, get_reporter
from providers import get_provider

logger = logging.getLogger(__name__)

DECISION_REQUEST_KEY = "__decision_request"
PROCEED_CHOICE = "Proceed"
CANCEL_CHOICE = "Cancel"


def _try_parse_todos(content: str) -> list[dict] | None:
    """Extract todos from LLM response."""
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


def _normalize_todos(raw: list) -> list[dict]:
    """Ensure each todo has id, title, status."""
    out = []
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


def _format_tools_brief(tools_brief: list) -> str:
    """Format tools_brief for prompt."""
    if not tools_brief:
        return ""
    lines = []
    for t in tools_brief[:40]:
        name = t.get("name", "")
        desc = (t.get("description") or "").strip()
        if name:
            lines.append(f"- {name}: {desc}" if desc else f"- {name}")
    return "\n".join(lines) if lines else ""


async def _produce_plan(question: str, tools_brief: list | None = None) -> tuple[list[dict], int]:
    """Call LLM to produce todo plan. Returns (todos, tokens_used)."""
    provider = get_provider()
    sys_prompt = (
        "You are a task planner. Given the user's request and available tools, "
        "produce a brief todo list as JSON. Use only tools from the Available tools list. "
        'Format: {"items": [{"id": "1", "title": "...", "status": "pending"}, ...]}. '
        "Keep 2-8 items. Use clear, actionable titles. All start as status: pending."
    )
    tools_text = _format_tools_brief(tools_brief or [])
    if tools_text:
        user_prompt = f"Task: {question}\n\nAvailable tools:\n{tools_text}\n\nTodo plan (JSON only):"
    else:
        user_prompt = f"Task: {question}\n\nTodo plan (JSON only):"
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
    raw = _try_parse_todos(content)
    todos = _normalize_todos(raw) if raw else []
    return todos, tokens


def main() -> None:
    params = json.loads(sys.stdin.read())
    args = params.get("arguments") or params
    question = str(args.get("question", "")).strip()
    decision_choice = args.get("_decision_choice", params.get("_decision_choice"))
    tools_brief = args.get("_tools_brief")
    if isinstance(tools_brief, list):
        pass
    else:
        tools_brief = None

    if not question:
        print(json.dumps({"error": "question is required"}, ensure_ascii=False))
        return

    logger.info("[todos.plan] question=%r tools_brief_count=%d", question[:80], len(tools_brief) if tools_brief else 0)
    result, plan_tokens = asyncio.run(_produce_plan(question, tools_brief=tools_brief))
    logger.info("[todos.plan] plan_items=%d decision_choice=%s tokens=%d", len(result), decision_choice or "(pending)", plan_tokens)

    # Phase 1: no confirmation yet — output __decision_request
    if not decision_choice:
        if not result:
            print(json.dumps({
                "error": "Failed to produce plan",
                "plan": [],
                "observation": "Could not parse a valid todo plan.",
                "tokens": plan_tokens,
            }, ensure_ascii=False))
            return

        plan_lines = [f"{t['id']}. {t['title']}" for t in result]
        message = "Plan:\n" + "\n".join(plan_lines) + "\n\nProceed with this plan?"
        reporter = get_reporter()
        if reporter:
            emit_event({"type": "TODOS_PLAN", "items": result})

        print(json.dumps({
            "plan": result,
            "observation": "\n".join(plan_lines),
            "tokens": plan_tokens,
            DECISION_REQUEST_KEY: {
                "message": message,
                "choices": [PROCEED_CHOICE, CANCEL_CHOICE],
                "payload": {"plan": result},
            },
        }, ensure_ascii=False))
        return

    # Phase 2: user chose Cancel
    if decision_choice == CANCEL_CHOICE:
        print(json.dumps({
            "plan": result,
            "observation": "User cancelled the plan.",
            "cancelled": True,
            "tokens": plan_tokens,
        }, ensure_ascii=False))
        return

    # Phase 2: user chose Proceed
    plan_lines = [f"{t['id']}. {t['title']}" for t in result]
    print(json.dumps({
        "plan": result,
        "observation": f"User confirmed. Proceed with:\n" + "\n".join(plan_lines),
        "confirmed": True,
        "tokens": plan_tokens,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
