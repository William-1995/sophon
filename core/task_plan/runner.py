"""
Execute task_plan.plan — LLM todo list + HITL (two-phase).

Runs in-process (no subprocess). Same JSON contract as the former todos skill script.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from constants import DECISION_REQUEST_KEY, SophonSkillEventType, TASK_PLAN_QUESTION_LOG_PREVIEW_MAX
from core.ipc import get_reporter
from core.task_plan.investigation import (
    discover_candidate_files,
    emit_task_plan_event,
    emit_thinking_trace,
    inspect_pdf_structure,
    looks_like_missing_file_input,
)

# Backward-compatible aliases for tests and any external hooks that still
# monkeypatch the old private helper names.
_discover_candidate_files = discover_candidate_files
_emit_task_plan_event = emit_task_plan_event
_emit_thinking_trace = emit_thinking_trace
_inspect_pdf_structure = inspect_pdf_structure
_looks_like_missing_file_input = looks_like_missing_file_input
from core.task_plan.parse import normalize_todo_items, parse_planner_response
from core.task_plan.prompts import SYSTEM_PROMPT, build_user_prompt, format_tools_brief
from providers import get_provider

logger = logging.getLogger(__name__)

PROCEED_CHOICE = "Proceed"
CANCEL_CHOICE = "Cancel"


async def _produce_plan(
    question: str,
    tools_brief: list[dict[str, str]] | None,
) -> tuple[list[dict[str, Any]], int, str | None, list[str]]:
    provider = get_provider()
    tools_text = format_tools_brief(tools_brief)
    user_prompt = build_user_prompt(question, tools_text)
    resp = await provider.chat(
        [{"role": "user", "content": user_prompt}],
        tools=None,
        system_prompt=SYSTEM_PROMPT,
    )
    usage = resp.get("usage") or {}
    tokens = usage.get("total_tokens", 0) or (
        usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
    )
    content = (resp.get("content") or "").strip()
    parsed = parse_planner_response(content)
    if not parsed:
        return [], int(tokens), None, []
    if parsed.get("mode") == "clarify":
        return [], int(tokens), str(parsed.get("message") or "").strip() or None, [
            str(item).strip()
            for item in (parsed.get("missing_inputs") or [])
            if str(item).strip()
        ]
    raw_items = parsed.get("items")
    items = normalize_todo_items(raw_items) if isinstance(raw_items, list) else []
    return items, int(tokens), None, []


async def execute_task_plan(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Phase 1 (no _decision_choice): build plan, emit TODOS_PLAN, return __decision_request.
    Phase 2 (_decision_choice set): use _decision_plan_snapshot when provided; else re-plan.
    """
    question = str(arguments.get("question", "")).strip()
    decision_choice = arguments.get("_decision_choice")
    plan_snapshot = arguments.get("_decision_plan_snapshot")

    tb = arguments.get("_tools_brief")
    tools_brief: list[dict[str, str]] | None = tb if isinstance(tb, list) else None
    event_sink = arguments.get("_event_sink")
    workspace_root = arguments.get("_workspace_root")
    missing_inputs = _looks_like_missing_file_input(question, tools_brief)
    candidate_files = _discover_candidate_files(question, workspace_root)
    if candidate_files and "file path" in missing_inputs and len(candidate_files) == 1:
        missing_inputs = [item for item in missing_inputs if item != "file path"]

    file_structure: dict[str, Any] | None = None
    pdf_candidates = [
        Path(workspace_root) / candidate
        for candidate in candidate_files
        if candidate.lower().endswith('.pdf')
    ]
    if pdf_candidates:
        for pdf_path in pdf_candidates[:1]:
            structure = _inspect_pdf_structure(pdf_path)
            if structure:
                file_structure = {
                    'path': pdf_path.relative_to(Path(workspace_root)).as_posix() if workspace_root else pdf_path.name,
                    **structure,
                }
                if structure.get('suggested_page_ranges'):
                    missing_inputs = [item for item in missing_inputs if item != 'file path']
                    if not candidate_files:
                        candidate_files = [file_structure['path']]
                    break

    investigation = _emit_thinking_trace(
        event_sink,
        question,
        tools_brief,
        missing_inputs,
        candidate_files,
        ready_for_planning=not missing_inputs,
        file_structure=file_structure,
    )

    if not question:
        return {"error": "question is required", "observation": "question is required"}

    if decision_choice:
        if str(decision_choice).strip() not in {PROCEED_CHOICE, CANCEL_CHOICE}:
            question = f"{question}\n\nAdditional user input: {decision_choice}"
        plan_tokens = 0
        if isinstance(plan_snapshot, list) and plan_snapshot:
            result = normalize_todo_items(plan_snapshot)
            clarify_message = None
            clarify_missing = []
        else:
            result, plan_tokens, clarify_message, clarify_missing = await _produce_plan(question, tools_brief=tools_brief)

        if clarify_message is not None:
            message = clarify_message
            if clarify_missing:
                message = message + ("\n- " + "\n- ".join(clarify_missing) if clarify_missing else "")
            return {
                "plan": [],
                "observation": message,
                "tokens": plan_tokens,
                DECISION_REQUEST_KEY: {
                    "message": message,
                    "choices": [],
                    "payload": {
                        "mode": "clarify",
                        "missing_inputs": clarify_missing,
                        "question": question,
                    },
                },
            }

        if decision_choice == CANCEL_CHOICE:
            logger.info("[task_plan] cancelled plan_items=%d", len(result))
            return {
                "plan": result,
                "observation": "User cancelled the plan.",
                "cancelled": True,
                "tokens": plan_tokens,
            }

        if decision_choice == PROCEED_CHOICE:
            try:
                emit_event({"type": SophonSkillEventType.PLAN_CONFIRMED})
            except Exception:
                pass
            plan_lines = [f"{t['id']}. {t['title']}" for t in result]
            logger.info("[task_plan] confirmed plan_items=%d tokens=%d", len(result), plan_tokens)
            return {
                "plan": result,
                "observation": "User confirmed. Proceed with:\n" + "\n".join(plan_lines),
                "confirmed": True,
                "tokens": plan_tokens,
            }

        return {
            "error": f"Unknown decision choice: {decision_choice!r}",
            "observation": f"Unknown choice: {decision_choice}",
        }


    if missing_inputs:
        message = "I need a little more information before I can plan:\n- " + "\n- ".join(missing_inputs)
        if candidate_files:
            message += "\n\nI found these possible files:\n- " + "\n- ".join(candidate_files)
        return {
            "plan": [],
            "observation": message,
            "tokens": 0,
            DECISION_REQUEST_KEY: {
                "message": message,
                "choices": [],
                "payload": {
                    "mode": "clarify",
                    "investigation_report": investigation,
                    "missing_inputs": missing_inputs,
                    "candidate_files": candidate_files,
                    "question": question,
                },
            },
        }

    result, plan_tokens, clarify_message, clarify_missing = await _produce_plan(question, tools_brief=tools_brief)
    logger.info(
        "[task_plan] phase1 question=%r tools_brief_count=%d plan_items=%d tokens=%d",
        question[:TASK_PLAN_QUESTION_LOG_PREVIEW_MAX],
        len(tools_brief) if tools_brief else 0,
        len(result),
        plan_tokens,
    )

    if clarify_message is not None:
        message = clarify_message
        if clarify_missing:
            message = message + ("\n- " + "\n- ".join(clarify_missing) if clarify_missing else "")
        investigation["inputs_missing"] = clarify_missing
        investigation["blocked_reasons"] = clarify_missing
        investigation["ready_for_planning"] = False
        investigation["recommended_next_action"] = "clarify"
        return {
            "plan": [],
            "observation": message,
            "tokens": plan_tokens,
            DECISION_REQUEST_KEY: {
                "message": message,
                "choices": [],
                "payload": {
                    "mode": "clarify",
                    "investigation_report": investigation,
                    "missing_inputs": clarify_missing,
                    "candidate_files": candidate_files,
                    "question": question,
                },
            },
        }

    if not result:
        return {
            "error": "Failed to produce plan",
            "plan": [],
            "observation": "Could not parse a valid todo plan.",
            "tokens": plan_tokens,
        }

    plan_lines = [f"{t['id']}. {t['title']}" for t in result]
    message = "Plan:\n" + "\n".join(plan_lines) + "\n\nProceed with this plan?"
    reporter = get_reporter()
    if reporter:
        emit_event({"type": "TODOS_PLAN", "items": result})
    _emit_task_plan_event(
        event_sink,
        {
            "type": "INVESTIGATION_REPORT",
            "payload": {
                **investigation,
                "ready_for_planning": True,
                "recommended_next_action": "plan",
                "planned_steps": plan_lines,
            },
        },
    )

    return {
        "plan": result,
        "observation": "\n".join(plan_lines),
        "tokens": plan_tokens,
        DECISION_REQUEST_KEY: {
            "message": message,
            "choices": [PROCEED_CHOICE, CANCEL_CHOICE],
            "payload": {
                "plan": result,
                "investigation_report": {
                    **investigation,
                    "ready_for_planning": True,
                    "recommended_next_action": "plan",
                    "planned_steps": plan_lines,
                },
            },
        },
    }
