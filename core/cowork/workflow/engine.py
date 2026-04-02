"""Execute workflow instances step-by-step with role-scoped ReAct prompts.

The engine builds cumulative context across completed steps, dispatches each step
according to its execution mode (tool/agent/multi_agent/discussion), persists state,
records timeline events, and validates generated workspace artifacts.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from config import get_config
from core.cowork.agent_base import AgentOutput, AgentStatus
from core.cowork.workflow.skill_roles import normalize_role_id, resolve_role_skills
from core.cowork.workflow.modes import StepStatus, WorkflowStatus
from core.cowork.workflow.state import (
    StepState,
    WorkflowState
)

from core.cowork.workflow.analysis import (
    build_batch_progress as _build_batch_progress,
    _ordered_step_ids as _ordered_step_ids,
)

from core.cowork.workflow.engine_support import WorkflowEngineSupport
from core.cowork.workflow.step_execution import WorkflowStepExecution



class WorkflowEngine:
    """Sequential workflow executor with persistence and timeline tracking."""

    def __init__(self) -> None:
        """Initialize in-memory cache, DB handle, and workspace paths."""
        self._instances: Dict[str, WorkflowState] = {}
        cfg = get_config()
        self._workspace_root = cfg.paths.user_workspace()
        self._db_path = cfg.paths.db_path()
        self._support = WorkflowEngineSupport(self._workspace_root)
        self._step_execution = WorkflowStepExecution(self._workspace_root, self._db_path)

    def create_instance(
        self,
        workflow_id: str,
        steps: List[Dict[str, Any]],
        input_data: Dict[str, Any],
    ) -> str:
        """Create a new workflow instance and persist initial state.

        Args:
            workflow_id (str): Workflow template id.
            steps (List[Dict[str, Any]]): Ordered step definitions.
            input_data (Dict[str, Any]): Workflow input payload.

        Returns:
            str: Generated instance id.

        Raises:
            ValueError: If any step definition is missing ``role``.
        """
        instance_id = f"wf_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow().isoformat()

        step_states: Dict[str, StepState] = {}
        for i, step_def in enumerate(steps):
            if "role" not in step_def:
                raise ValueError("each step must include 'role'")
            role = normalize_role_id(str(step_def["role"]))
            step_id = f"step_{i}"
            execution_mode = str(step_def.get("execution_mode", "tool")).lower()
            base_input: Dict[str, Any] = {
                "task": str(step_def.get("task", "")),
                "role": role,
                "skills": step_def.get("skills", []),
                "data": input_data if i == 0 else {},
            }
            for field in ("agent_config", "multi_agent_config", "discussion_config"):
                if field in step_def:
                    base_input[field] = step_def[field]
            base_input["execution_mode"] = execution_mode

            step_states[step_id] = StepState(
                step_id=step_id,
                name=str(step_def.get("task", f"Step {i}"))[:50],
                status=StepStatus.PENDING,
                execution_mode=execution_mode,
                input_data=base_input,
                created_at=now,
            )

        state = WorkflowState(
            workflow_id=workflow_id,
            instance_id=instance_id,
            status=WorkflowStatus.QUEUED,
            steps=step_states,
            current_step_id="step_0",
            created_at=now,
            input_data=input_data,
        )
        state.batch_progress = _build_batch_progress(
            input_data,
            step_states,
            current_step_id=state.current_step_id,
            workflow_status=state.status,
        )
        if state.batch_progress:
            state.add_timeline_event(
                event_type="batch_detected",
                payload=state.batch_progress,
            )

        state.add_timeline_event(
            event_type="workflow_created",
            payload={
                "workflow_id": workflow_id,
                "steps": list(step_states.keys()),
            },
        )

        self._instances[instance_id] = state
        self._support._save_instance_to_db(state)

        return instance_id

    async def execute_instance(self, instance_id: str) -> WorkflowState:
        """Run all workflow steps sequentially until completion or first failure.

        Args:
            instance_id (str): Workflow instance id.

        Returns:
            WorkflowState: Final (or early-failed) workflow state.

        Raises:
            ValueError: If the instance cannot be found in memory or storage.
        """
        state = self._instances.get(instance_id) or self._support._load_instance_from_db(instance_id)
        if not state:
            raise ValueError(f"Instance not found: {instance_id}")

        self._support._start_workflow_run(state)

        try:
            for step_id in _ordered_step_ids(state.steps):
                step = state.steps[step_id]
                self._support._start_step_run(state, step)

                result = await self._execute_step(state, step)
                step.status = StepStatus.COMPLETED if result.status == AgentStatus.COMPLETED else StepStatus.FAILED
                step.completed_at = datetime.utcnow().isoformat()
                step.output_data = result.result
                step.error_message = result.error

                if step.status == StepStatus.COMPLETED:
                    artifact_error = self._support._record_step_artifacts(state, step)
                    if artifact_error:
                        step.status = StepStatus.FAILED
                        step.error_message = artifact_error
                        self._support._finalize_failed_step(state, step, artifact_error, "step_failed")
                        return state

                state.batch_progress = _build_batch_progress(
                    state.input_data,
                    state.steps,
                    current_step_id=state.current_step_id,
                    workflow_status=state.status,
                )
                self._support._save_instance_to_db(state)

                if step.status == StepStatus.FAILED:
                    self._support._finalize_failed_step(state, step, result.error or "step failed", "step_failed")
                    return state

                state.add_timeline_event(
                    event_type="step_completed",
                    step_id=step.step_id,
                    payload={
                        "agent_id": step.agent_id,
                        "agent_ids": step.agent_ids,
                        "output_present": bool(step.output_data),
                    },
                )
                state.batch_progress = _build_batch_progress(
                    state.input_data,
                    state.steps,
                    current_step_id=state.current_step_id,
                    workflow_status=state.status,
                )
                self._support._save_instance_to_db(state)

            self._support._finalize_workflow_success(state)

        except Exception as e:
            logger.exception("Workflow execution failed: %s", e)
            self._support._finalize_failed_step(state, StepState(step_id=state.current_step_id or "workflow", name="workflow"), str(e), "workflow_failed")

        return state


    async def _execute_step(self, state: WorkflowState, step: StepState) -> AgentOutput:
        """Dispatch one step to the shared step-execution helper."""
        step_config = step.input_data
        role_raw = step_config.get("role")
        if not role_raw:
            return AgentOutput(
                status=AgentStatus.FAILED,
                result={},
                error="step missing role",
            )
        role = normalize_role_id(str(role_raw))
        override = step_config.get("skills")
        override_list: list[str] | None = None
        if isinstance(override, list) and override:
            override_list = [str(x).strip() for x in override if str(x).strip()]
        _, primary_skills, role_instruction = resolve_role_skills(role, override_list)
        return await self._step_execution.run_step(state, step, primary_skills, role_instruction)

    def get_instance(self, instance_id: str) -> Optional[WorkflowState]:
        """Return cached or persisted workflow instance by id.

        Args:
            instance_id (str): Workflow instance id.

        Returns:
            Optional[WorkflowState]: Instance state when found.
        """
        if instance_id in self._instances:
            return self._instances[instance_id]
        return self._support._load_instance_from_db(instance_id)
