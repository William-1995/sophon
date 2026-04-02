"""Workflow engine support helpers.

Keeps lifecycle, persistence, and artifact handling out of the main orchestrator.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.cowork.workflow.analysis import (
    build_batch_progress as _build_batch_progress,
    extract_output_paths as _extract_output_paths,
    scan_recent_files as _scan_recent_files,
    task_requests_file_output as _task_requests_file_output,
)
from core.cowork.workflow.modes import StepStatus, WorkflowStatus
from core.cowork.workflow.state import StepState, WorkflowState
from db.workflow_repository import (
    load_workflow_state as _load_workflow_state,
    save_workflow_artifacts as _save_workflow_artifacts,
    save_workflow_state as _save_workflow_state,
)

logger = logging.getLogger(__name__)


class WorkflowEngineSupport:
    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root
        self._db = None

    def _get_db(self):
        """Lazily create and cache a DB connection used for workflow persistence."""
        if self._db is None:
            from db.schema import get_connection

            self._db = get_connection()
        return self._db

    def _workspace_relative_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self._workspace_root.resolve()))
        except ValueError:
            return str(path.resolve())

    def _record_step_artifacts(self, state: WorkflowState, step: StepState) -> str | None:
        """Validate and persist file artifacts declared by a completed step."""
        task_text = str(step.input_data.get("task") or step.name or "")
        if not _task_requests_file_output(task_text):
            return None

        output_paths = [Path(path) for path in _extract_output_paths(step.output_data)]
        started_at = step.started_at or state.started_at or state.created_at
        try:
            started_dt = datetime.fromisoformat(str(started_at))
        except ValueError:
            started_dt = datetime.utcnow()

        if not output_paths:
            output_paths = _scan_recent_files(self._workspace_root, started_dt)[:1]

        if not output_paths:
            return (
                "Workflow step requested a file output but no artifact was written to the workspace. "
                "Please rerun with a concrete save path or a write-capable step."
            )

        resolved_paths: list[Path] = []
        for raw_path in output_paths:
            resolved = raw_path if raw_path.is_absolute() else (self._workspace_root / raw_path)
            resolved = resolved.resolve()
            if not resolved.exists():
                continue
            try:
                resolved.relative_to(self._workspace_root.resolve())
            except ValueError:
                return f"Artifact path escapes workspace: {resolved}"
            resolved_paths.append(resolved)

        if not resolved_paths:
            return "Workflow step reported a file output, but the referenced artifact was not found in the workspace."

        if isinstance(step.output_data, dict):
            rel_paths = [self._workspace_relative_path(path) for path in resolved_paths]
            if len(rel_paths) == 1:
                step.output_data.setdefault("output_file", rel_paths[0])
            else:
                step.output_data.setdefault("output_files", rel_paths)
            step.output_data.setdefault("artifacts", rel_paths)

        try:
            conn = self._get_db()
            artifact_rows = [
                {
                    "file_path": self._workspace_relative_path(resolved),
                    "file_type": resolved.suffix.lstrip(".").lower() or None,
                    "file_size": resolved.stat().st_size,
                    "is_intermediate": step.status != StepStatus.COMPLETED,
                }
                for resolved in resolved_paths
            ]
            _save_workflow_artifacts(conn, state, step, artifact_rows)
        except Exception as exc:
            logger.warning("Failed to persist workflow artifact metadata: %s", exc)
        return None

    def _save_instance_to_db(self, state: WorkflowState) -> None:
        try:
            conn = self._get_db()
            _save_workflow_state(conn, state)
        except Exception as e:
            logger.error("Failed to save instance to DB: %s", e)

    def _load_instance_from_db(self, instance_id: str) -> Optional[WorkflowState]:
        try:
            conn = self._get_db()
            return _load_workflow_state(conn, instance_id)
        except Exception as e:
            logger.error("Failed to load instance from DB: %s", e)
        return None

    def _start_workflow_run(self, state: WorkflowState) -> None:
        now = datetime.utcnow().isoformat()
        state.status = WorkflowStatus.RUNNING
        state.started_at = now
        state.batch_progress = _build_batch_progress(
            state.input_data,
            state.steps,
            current_step_id=state.current_step_id,
            workflow_status=state.status,
        )
        self._save_instance_to_db(state)
        state.add_timeline_event(
            event_type="workflow_started",
            payload={"current_step_id": state.current_step_id},
        )
        self._save_instance_to_db(state)

    def _start_step_run(self, state: WorkflowState, step: StepState) -> None:
        state.current_step_id = step.step_id
        step.status = StepStatus.RUNNING
        step.started_at = datetime.utcnow().isoformat()
        state.batch_progress = _build_batch_progress(
            state.input_data,
            state.steps,
            current_step_id=state.current_step_id,
            workflow_status=state.status,
        )
        self._save_instance_to_db(state)
        state.add_timeline_event(
            event_type="step_started",
            step_id=step.step_id,
            payload={"name": step.name, "execution_mode": step.execution_mode},
        )
        self._save_instance_to_db(state)

    def _finalize_failed_step(
        self,
        state: WorkflowState,
        step: StepState,
        error: str,
        event_type: str,
    ) -> None:
        state.status = WorkflowStatus.FAILED
        state.error_message = error
        state.completed_at = datetime.utcnow().isoformat()
        state.batch_progress = _build_batch_progress(
            state.input_data,
            state.steps,
            current_step_id=state.current_step_id,
            workflow_status=state.status,
        )
        self._save_instance_to_db(state)
        state.add_timeline_event(
            event_type=event_type,
            step_id=step.step_id,
            payload={"error": error},
        )
        self._save_instance_to_db(state)

    def _finalize_workflow_success(self, state: WorkflowState) -> None:
        state.status = WorkflowStatus.COMPLETED
        state.completed_at = datetime.utcnow().isoformat()
        state.batch_progress = _build_batch_progress(
            state.input_data,
            state.steps,
            current_step_id=state.current_step_id,
            workflow_status=state.status,
        )
        self._save_instance_to_db(state)
        state.add_timeline_event(
            event_type="workflow_completed",
            payload={"steps": list(state.steps.keys())},
        )
        self._save_instance_to_db(state)
