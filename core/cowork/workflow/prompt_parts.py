"""Workflow prompt fragments.

Keep prompt composition helpers out of the engine so the orchestrator can focus on
state transitions and dispatch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.cowork.workflow.state import StepState, WorkflowState

_WORKFLOW_CONTEXT_JSON_MAX = 120_000


def build_cumulative_context(
    state: WorkflowState,
    current_step_id: str,
    initial_step_data: Any,
) -> Any:
    """Build cumulative context visible to the current step prompt."""
    ordered = _ordered_step_ids(state.steps)
    try:
        idx = ordered.index(current_step_id)
    except ValueError:
        idx = 0
    if idx == 0:
        return initial_step_data
    prior: dict[str, Any] = {}
    for pid in ordered[:idx]:
        st = state.steps.get(pid)
        if st and st.output_data:
            prior[pid] = st.output_data
    return {
        "workflow_input": dict(state.input_data),
        "step_outputs": prior,
    }


def build_step_header_fragment(step: StepState, current_time: str) -> str:
    return (
        f"## Current time\n{current_time}\n"
        f"## Workflow step ({step.input_data.get('role')})\n{step.input_data.get('task', '(no task text)')}\n"
    )


def build_context_fragment(context: Any) -> str | None:
    if not context:
        return None
    blob = _json_context_for_prompt(context)
    return (
        "## Context (JSON)\n"
        "Previous steps' outputs are available under `step_outputs`.\n"
        "Include workflow_input for the original args.\n\n"
        f"{blob}"
    )


def build_batch_fragment(batch_summary: dict[str, Any] | None) -> str | None:
    if not batch_summary:
        return None
    batch_contract = json.dumps(batch_summary["batch_contract"], ensure_ascii=False, default=str)
    return "\n".join([
        "## Batch contract",
        f"- Batch mode: {batch_summary['batch_kind']} ({batch_summary['batch_count']} items)",
        f"- Preview: {', '.join(batch_summary['batch_preview'])}",
        f"- Batch contract: {batch_contract}",
        "- Continue through the remaining items even if one item fails or the network is flaky.",
        "- Partial results are allowed, but the step is not complete until every item has been attempted.",
        "- Return successes and failures separately so the user can audit what happened.",
        "",
        "Important: never collapse the batch into a single representative item.",
    ])


def build_file_output_fragment(requested: bool) -> str | None:
    if not requested:
        return None
    return "\n".join([
        "## File output contract",
        "- This step must persist a real file in the workspace.",
        "- Do not claim success unless the file exists after the write.",
        "- Return the saved relative path in the final structured output.",
    ])


def build_system_extra_prefix(
    agent_label: str | None,
    role_instruction: str,
    current_time: str,
    instance_id: str,
) -> str:
    agent_prefix = f"{agent_label}\n\n" if agent_label else ""
    return (
        f"{agent_prefix}"
        f"{role_instruction}\n\n"
        f"Current time: {current_time}\n"
        f"Workflow instance `{instance_id}`. Use only the tools you are given.\n"
        "Later steps receive cumulative outputs under `step_outputs`."
    )


def _json_context_for_prompt(obj: Any) -> str:
    try:
        blob = json.dumps(obj, ensure_ascii=False, default=str)
    except TypeError:
        blob = str(obj)
    if len(blob) > _WORKFLOW_CONTEXT_JSON_MAX:
        blob = blob[:_WORKFLOW_CONTEXT_JSON_MAX] + "\n...[truncated for workflow context size limit]"
    return blob


def _ordered_step_ids(steps: dict[str, StepState]) -> list[str]:
    ordered = list(steps.keys())
    ordered.sort(key=_step_sort_key)
    return ordered


def _step_sort_key(step_id: str) -> tuple[int, str]:
    if step_id.startswith("step_"):
        try:
            return int(step_id.split("_", 1)[1]), step_id
        except ValueError:
            pass
    return 10**9, step_id
