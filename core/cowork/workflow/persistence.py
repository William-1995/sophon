"""Workflow serialization helpers.

Keep SQL and storage concerns out of this module.
"""

from __future__ import annotations

import json
from typing import Any

from core.cowork.workflow.state import StepState, WorkflowState


def workflow_state_payload(state: WorkflowState) -> dict[str, Any]:
    return {
        "steps": {sid: st.to_dict() for sid, st in state.steps.items()},
        "agents": {aid: agent.to_dict() for aid, agent in state.agents.items()},
        "messages": [msg.to_dict() for msg in state.messages],
        "threads": {tid: thread.to_dict() for tid, thread in state.threads.items()},
        "timeline": [evt.to_dict() for evt in state.timeline],
        "batch_progress": state.batch_progress,
    }


def workflow_state_json(state: WorkflowState) -> str:
    return json.dumps(workflow_state_payload(state))


def workflow_step_output_path(step: StepState) -> str | None:
    output_artifact_path = None
    if isinstance(step.output_data, dict):
        output_artifact_path = step.output_data.get("output_file")
        if not output_artifact_path:
            output_files = step.output_data.get("output_files")
            if isinstance(output_files, list) and output_files:
                output_artifact_path = output_files[0]
    return output_artifact_path
