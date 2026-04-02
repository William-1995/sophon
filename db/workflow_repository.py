"""Workflow persistence repository."""

from __future__ import annotations

import json
from datetime import datetime
import uuid
from typing import Any, Dict, List

from core.cowork.workflow.modes import StepStatus, WorkflowStatus
from core.cowork.workflow.persistence import (
    workflow_state_json,
    workflow_step_output_path,
)
from core.cowork.workflow.state import (
    AgentState,
    MessageEntry,
    StepState,
    ThreadState,
    TimelineEvent,
    WorkflowState,
)


def _parse_json_blob(blob: Any) -> dict[str, Any]:
    if not blob:
        return {}
    if isinstance(blob, dict):
        return blob
    if isinstance(blob, str):
        try:
            parsed = json.loads(blob)
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _build_step_from_row(step_row: Any) -> StepState:
    sid = step_row[2]
    out_obj = _parse_json_blob(step_row[8])
    return StepState(
        step_id=sid,
        name="",
        status=StepStatus(step_row[6]) if step_row[6] else StepStatus.PENDING,
        input_data={"role": (step_row[3] or "").strip(), "task": "", "skills": [], "data": {}},
        output_data=out_obj,
        error_message=step_row[9],
        created_at=step_row[12],
        started_at=step_row[13],
        completed_at=step_row[14],
    )


def workflow_state_from_db_row(row: Any, step_rows: List[Any] | None = None) -> WorkflowState:
    steps: Dict[str, StepState] = {}
    agents: Dict[str, AgentState] = {}
    messages: List[MessageEntry] = []
    threads: Dict[str, ThreadState] = {}
    timeline_data: List[dict[str, Any]] = []
    batch_progress: Dict[str, Any] = {}

    state_blob = row[6]
    if state_blob:
        try:
            parsed = json.loads(state_blob) if isinstance(state_blob, str) else state_blob
            if isinstance(parsed, dict):
                batch_progress = parsed.get("batch_progress") if isinstance(parsed.get("batch_progress"), dict) else {}
                raw_steps = parsed.get("steps") or {}
                for sid, sd in raw_steps.items():
                    if isinstance(sd, dict):
                        steps[sid] = StepState.from_dict(sd)
                raw_agents = parsed.get("agents") or {}
                for aid, adata in raw_agents.items():
                    if isinstance(adata, dict):
                        agents[aid] = AgentState.from_dict(adata)
                raw_messages = parsed.get("messages") or []
                for msg_obj in raw_messages:
                    if isinstance(msg_obj, dict):
                        messages.append(MessageEntry.from_dict(msg_obj))
                raw_threads = parsed.get("threads") or {}
                for tid, th_obj in raw_threads.items():
                    if isinstance(th_obj, dict):
                        thread = ThreadState(
                            thread_id=tid,
                            topic=str(th_obj.get("topic", "")),
                            participant_ids=list(th_obj.get("participant_ids", [])),
                        )
                        thread.consensus_reached = bool(th_obj.get("consensus_reached"))
                        thread.consensus_result = th_obj.get("consensus_result")
                        thread.started_at = th_obj.get("started_at", thread.started_at)
                        thread.completed_at = th_obj.get("completed_at")
                        raw_thread_messages = th_obj.get("messages") or []
                        thread.messages = [
                            MessageEntry.from_dict(m)
                            for m in raw_thread_messages
                            if isinstance(m, dict)
                        ]
                        threads[tid] = thread
                timeline_data = parsed.get("timeline") or []
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            steps = {}

    if not steps and step_rows:
        for step_row in step_rows:
            steps[step_row[2]] = _build_step_from_row(step_row)

    return WorkflowState(
        workflow_id=row[1],
        instance_id=row[0],
        status=WorkflowStatus(row[3]),
        steps=steps,
        agents=agents,
        messages=messages,
        threads=threads,
        timeline=[
            TimelineEvent.from_dict(evt)
            for evt in timeline_data
            if isinstance(evt, dict)
        ],
        batch_progress=batch_progress,
        current_step_id=row[4],
        created_at=row[9],
        started_at=row[10],
        completed_at=row[11],
        error_message=row[8],
        input_data=_parse_json_blob(row[5]),
    )


def save_workflow_state(conn: Any, state: WorkflowState) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO workflow_instances
        (instance_id, workflow_id, parent_session_id, status, current_step_id,
         input_data_json, state_json, output_data_json, error_message,
         created_at, started_at, completed_at)
        VALUES (?, ?, NULL, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
        """,
        (
            state.instance_id,
            state.workflow_id,
            state.status.value,
            state.current_step_id,
            json.dumps(state.input_data),
            workflow_state_json(state),
            state.error_message,
            state.created_at,
            state.started_at,
            state.completed_at,
        ),
    )

    for step_id, step in state.steps.items():
        cursor.execute(
            """
            INSERT OR REPLACE INTO workflow_step_executions
            (execution_id, instance_id, step_id, agent_type,
             input_artifact_path, output_artifact_path, status, retry_count,
             output_data_json, error_message, convergence_status, log_session_id,
             created_at, started_at, completed_at)
            VALUES (?, ?, ?, ?, NULL, ?, ?, 0, ?, ?, NULL, NULL, ?, ?, ?)
            """,
            (
                f"{state.instance_id}_{step_id}",
                state.instance_id,
                step_id,
                step.input_data.get("role", ""),
                workflow_step_output_path(step),
                step.status.value,
                json.dumps(step.output_data) if step.output_data else None,
                step.error_message,
                step.created_at,
                step.started_at,
                step.completed_at,
            ),
        )

    conn.commit()


def save_workflow_artifacts(conn: Any, state: WorkflowState, step: StepState, artifact_paths: list[dict[str, Any]]) -> None:
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM workflow_artifacts WHERE instance_id = ? AND step_id = ?",
        (state.instance_id, step.step_id),
    )
    for artifact in artifact_paths:
        rel_path = str(artifact.get("file_path") or "").strip()
        if not rel_path:
            continue
        cursor.execute(
            """
            INSERT OR REPLACE INTO workflow_artifacts
            (artifact_id, instance_id, step_id, file_path, file_type, file_size,
             schema_name, is_intermediate, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL)
            """,
            (
                f"{state.instance_id}_{step.step_id}_{uuid.uuid5(uuid.NAMESPACE_URL, rel_path).hex}",
                state.instance_id,
                step.step_id,
                rel_path,
                str(artifact.get("file_type") or "").strip() or None,
                artifact.get("file_size"),
                bool(artifact.get("is_intermediate", step.status != StepStatus.COMPLETED)),
                datetime.utcnow().timestamp(),
            ),
        )
    conn.commit()


def load_workflow_state(conn: Any, instance_id: str):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workflow_instances WHERE instance_id = ?", (instance_id,))
    row = cursor.fetchone()
    if not row:
        return None

    cursor.execute(
        "SELECT * FROM workflow_step_executions WHERE instance_id = ?",
        (instance_id,),
    )
    step_rows = cursor.fetchall()
    return workflow_state_from_db_row(row, step_rows)
