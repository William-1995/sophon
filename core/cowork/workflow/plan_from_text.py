"""
Build workflow steps from natural language via the configured LLM (strict JSON).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from core.cowork.workflow.skill_roles import list_role_ids, normalize_role_id
from providers import get_provider

logger = logging.getLogger(__name__)

_MAX_DESC = 8000


class WorkflowPlanError(Exception):
    """LLM did not return a valid plan."""


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            return None
    return None


async def plan_workflow_steps_from_description(description: str, uploaded_files: list[str] | None = None) -> list[dict[str, Any]]:
    """
    Returns [{"role": str, "task": str, "skills"?: list[str]}, ...].

    Raises:
        WorkflowPlanError: empty description, invalid LLM output, or unknown role.
    """
    desc = (description or "").strip()
    if not desc:
        raise WorkflowPlanError("description is empty")

    allowed = list_role_ids()
    if not allowed:
        raise WorkflowPlanError("no workflow roles available; install/enable workflow agents first")
    roles_csv = ", ".join(allowed)
    file_note = ""
    normalized_files = [str(path).strip() for path in (uploaded_files or []) if str(path).strip()]
    if normalized_files:
        file_note = (
            "Uploaded files for this workflow:\n"
            + "\n".join(f"- {path}" for path in normalized_files)
            + "\nUse these as the default file context when planning."
        )
    system = (
        "You output ONLY a JSON object, no markdown. Schema:\n"
        '{"steps":[{"role":"<role_id>","task":"<instruction>"}]}\n'
        f"role_id must be exactly one of: {roles_csv}.\n"
        "Choose roles by stage intent, not by hardcoded tool assumptions. "
        "Each task must describe desired outcome and acceptance criteria clearly. "
        "Typically 1-5 steps; keep each step focused and executable. "
        "When the request refers to lists, rows, URLs, files, or other collections, preserve the batch nature in the step tasks. "
        "Do not collapse a collection into a single representative example. If one item fails, continue with the remaining items and note the failure. "
        "If a step must handle multiple items, make that explicit in the task text."
    )
    if file_note:
        system = f"{file_note}\n\n{system}"

    truncated = desc[:_MAX_DESC]
    provider = get_provider()
    resp = await provider.chat(
        [{"role": "user", "content": truncated}],
        system_prompt=system,
    )
    content = (resp.get("content") or "").strip()
    data = _extract_json_object(content)
    if not data:
        raise WorkflowPlanError("model returned no parseable JSON object")

    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise WorkflowPlanError("JSON must contain non-empty 'steps' array")

    out: list[dict[str, Any]] = []
    for item in raw_steps:
        if not isinstance(item, dict):
            continue
        if "role" not in item:
            raise WorkflowPlanError("each step must have 'role'")
        rid = normalize_role_id(str(item["role"]))
        task = str(item.get("task", "")).strip()
        if not task:
            raise WorkflowPlanError(f"step with role {rid!r} must have non-empty 'task'")
        step: dict[str, Any] = {"role": rid, "task": task}
        sk = item.get("skills")
        if isinstance(sk, list) and sk:
            step["skills"] = [str(x).strip() for x in sk if str(x).strip()]
        out.append(step)

    if not out:
        raise WorkflowPlanError("no valid steps after parsing")

    logger.info("[workflow_plan] llm steps=%d", len(out))
    return out
