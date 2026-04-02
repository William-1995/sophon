"""Workflow orchestrator for investigate-first collaboration (compatibility layer).

Use this package for explicit collaboration protocol experiments; the main
workflow execution engine lives under `core.cowork.workflow`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from core.tools import tool_catalog

from .modes import CollaborationMessageKind, RoundStatus, ToolStepStatus, WorkflowStatus
from .records import InvestigationReport
from .state import MessageRecord, RoundRecord, ToolStepRecord, WorkflowState


@dataclass(frozen=True)
class PlannedToolStep:
    tool_name: str
    arguments: dict[str, Any]
    requested_by: str
    purpose: str = ""


class WorkflowOrchestrator:
    """Coordinates visible investigation, planning, and explicit tool execution."""

    def __init__(
        self,
        workflow_id: str,
        task: str,
        *,
        catalog=tool_catalog,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.state = WorkflowState(
            workflow_id=workflow_id,
            task=task,
            metadata=dict(metadata or {}),
        )
        self.catalog = catalog

    def start_round(self, owner: str, objective: str, metadata: dict[str, Any] | None = None) -> RoundRecord:
        return self.state.start_round(owner, objective, metadata=metadata)

    def begin_thinking(
        self,
        owner: str,
        objective: str,
        *,
        thoughts: Sequence[tuple[str, str]] = (),
        metadata: dict[str, Any] | None = None,
    ) -> RoundRecord:
        reusable_round = self._existing_thinking_round()
        round_state = reusable_round or self.state.begin_thinking(owner, objective, metadata=metadata)
        for sender, content in thoughts:
            self.record_thought(sender, content, round_id=round_state.round_id, metadata=metadata)
        return round_state

    def record_investigation(
        self,
        owner: str,
        objective: str,
        report: InvestigationReport,
        *,
        thoughts: Sequence[tuple[str, str]] = (),
        metadata: dict[str, Any] | None = None,
    ) -> InvestigationReport:
        round_state = self.begin_thinking(owner, objective, thoughts=thoughts, metadata=metadata)
        return self.state.set_investigation_report(round_state.round_id, report)

    def plan_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        requested_by: str,
        round_id: str | None = None,
        purpose: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ToolStepRecord:
        round_state = round_id or self.state.active_round_id
        if round_state is None:
            raise ValueError("tool plan requires an active round")
        return self.state.add_tool_step(
            tool_name=tool_name,
            arguments=arguments,
            requested_by=requested_by,
            round_id=round_state,
            purpose=purpose,
            metadata=metadata,
        )

    def record_thought(
        self,
        sender: str,
        content: str,
        *,
        round_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MessageRecord:
        return self.state.add_message(CollaborationMessageKind.THOUGHT, sender, content, round_id, metadata)

    def record_question(
        self,
        sender: str,
        content: str,
        *,
        round_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MessageRecord:
        return self.state.add_message(CollaborationMessageKind.QUESTION, sender, content, round_id, metadata)

    def request_clarification(
        self,
        owner: str,
        objective: str,
        question: str,
        *,
        sender: str = "orchestrator",
        metadata: dict[str, Any] | None = None,
    ) -> RoundRecord:
        reusable_round = self._existing_clarification_round(question)
        if reusable_round is not None:
            self.state.active_round_id = reusable_round.round_id
            self.state.metadata["clarification_reused"] = True
            self.state.metadata["clarification_round_id"] = reusable_round.round_id
            self.state.touch()
            return reusable_round
        self.state.metadata["clarification_reused"] = False
        return self.state.require_clarification(
            owner,
            objective,
            question,
            sender=sender,
            metadata=metadata,
        )

    def record_answer(
        self,
        sender: str,
        content: str,
        *,
        round_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MessageRecord:
        return self.state.add_message(CollaborationMessageKind.ANSWER, sender, content, round_id, metadata)

    def record_decision(
        self,
        sender: str,
        content: str,
        *,
        round_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MessageRecord:
        return self.state.add_message(CollaborationMessageKind.DECISION, sender, content, round_id, metadata)

    def record_final(
        self,
        sender: str,
        content: str,
        *,
        round_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MessageRecord:
        return self.state.add_message(CollaborationMessageKind.FINAL, sender, content, round_id, metadata)

    def request_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        requested_by: str,
        round_id: str | None = None,
        purpose: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ToolStepRecord:
        round_state = round_id or self.state.active_round_id
        if round_state is None:
            raise ValueError("tool request requires an active round")
        self.state.set_round_status(round_state, RoundStatus.AWAITING_TOOL)
        self.state.set_status(WorkflowStatus.EXECUTING)
        self.state.add_message(
            CollaborationMessageKind.TOOL_REQUEST,
            requested_by,
            f"{tool_name} requested",
            round_id=round_state,
            metadata={"tool_name": tool_name, "arguments": dict(arguments), **(metadata or {})},
        )
        return self.state.add_tool_step(
            tool_name=tool_name,
            arguments=arguments,
            requested_by=requested_by,
            round_id=round_state,
            purpose=purpose,
            metadata=metadata,
        )

    def plan_round(
        self,
        owner: str,
        objective: str,
        planned_tools: Sequence[PlannedToolStep] = (),
        *,
        messages: Sequence[tuple[CollaborationMessageKind, str, str]] = (),
        allow_replan: bool = False,
    ) -> RoundRecord:
        self._ensure_planning_ready()
        reusable_round = self._existing_plan_round()
        if reusable_round is not None and not allow_replan:
            self.state.active_round_id = reusable_round.round_id
            self.state.metadata["plan_reused"] = True
            self.state.metadata["plan_reused_round_id"] = reusable_round.round_id
            self.state.touch()
            return reusable_round

        round_state = self._activate_planning_round(owner, objective)
        self.state.metadata["plan_reused"] = False
        self.state.set_status(WorkflowStatus.PLANNING)
        for kind, sender, content in messages:
            self.state.add_message(kind, sender, content, round_id=round_state.round_id)
        for step in planned_tools:
            self.plan_tool(
                step.tool_name,
                step.arguments,
                requested_by=step.requested_by,
                round_id=round_state.round_id,
                purpose=step.purpose,
            )
        return round_state

    async def execute_planned_tools(self, round_id: str | None = None) -> list[ToolStepRecord]:
        target_round = round_id or self.state.active_round_id
        if target_round is None:
            return []
        executed: list[ToolStepRecord] = []
        for step in self._planned_steps_for_round(target_round):
            executed.append(await self._execute_step(step))
            if self.state.status == WorkflowStatus.FAILED:
                break
        return executed

    async def run_round(
        self,
        owner: str,
        objective: str,
        planned_tools: Sequence[PlannedToolStep] = (),
        *,
        investigation_report: InvestigationReport | None = None,
        thoughts: Sequence[tuple[str, str]] = (),
        messages: Sequence[tuple[CollaborationMessageKind, str, str]] = (),
        allow_replan: bool = False,
        auto_execute: bool = False,
    ) -> WorkflowState:
        if investigation_report is None:
            self.begin_thinking(owner, objective, thoughts=thoughts)
        else:
            self.record_investigation(
                owner,
                objective,
                investigation_report,
                thoughts=thoughts,
            )
        round_state = self.plan_round(
            owner,
            objective,
            planned_tools,
            messages=messages,
            allow_replan=allow_replan,
        )
        if auto_execute:
            await self.execute_round(round_state.round_id)
        return self.state

    async def execute_round(self, round_id: str) -> WorkflowState:
        self.state.set_status(WorkflowStatus.EXECUTING)
        round_record = self.state._get_round(round_id)
        for step in self._planned_steps_for_round(round_record.round_id):
            self.state.set_round_status(round_record.round_id, RoundStatus.AWAITING_TOOL)
            self.state.add_message(
                CollaborationMessageKind.TOOL_REQUEST,
                step.requested_by,
                f"{step.tool_name} requested",
                round_id=round_record.round_id,
                metadata={"tool_name": step.tool_name, "arguments": dict(step.arguments), "step_id": step.step_id},
            )
            await self._execute_step(step)
            if self.state.status == WorkflowStatus.FAILED:
                return self.state
        self.state.set_round_status(round_record.round_id, RoundStatus.SYNTHESIZING)
        self.state.complete_round(round_record.round_id)
        self.state.set_status(WorkflowStatus.SYNTHESIZING)
        self.state.mark_completed(self.state.final_summary)
        return self.state

    async def _execute_step(self, step: ToolStepRecord) -> ToolStepRecord:
        tool = self.catalog.get(step.tool_name)
        if tool is None:
            step.fail(f"unknown tool: {step.tool_name}")
            self.state.add_message(
                CollaborationMessageKind.TOOL_ERROR,
                step.requested_by,
                step.error or "unknown tool",
                round_id=step.round_id,
                metadata={"tool_name": step.tool_name, "step_id": step.step_id},
            )
            self.state.set_round_status(step.round_id, RoundStatus.BLOCKED, reason=step.error or "")
            self.state.mark_failed(step.error or f"unknown tool: {step.tool_name}")
            return step

        step.start()
        self.state.add_message(
            CollaborationMessageKind.TOOL_START,
            step.requested_by,
            f"{step.tool_name} started",
            round_id=step.round_id,
            metadata={"tool_name": step.tool_name, "step_id": step.step_id},
        )
        try:
            result = await tool.execute(**step.arguments)
        except Exception as exc:  # pragma: no cover - tool failures are runtime dependent
            step.fail(str(exc))
            self.state.add_message(
                CollaborationMessageKind.TOOL_ERROR,
                step.requested_by,
                str(exc),
                round_id=step.round_id,
                metadata={"tool_name": step.tool_name, "step_id": step.step_id},
            )
            self.state.block_round(step.round_id, str(exc))
            self.state.mark_failed(str(exc))
            return step

        step.complete(result)
        self.state.add_message(
            CollaborationMessageKind.TOOL_RESULT,
            step.requested_by,
            f"{step.tool_name} completed",
            round_id=step.round_id,
            metadata={"tool_name": step.tool_name, "step_id": step.step_id, "result": result},
        )
        return step

    def _planned_steps_for_round(self, round_id: str) -> list[ToolStepRecord]:
        return [
            step
            for step in self.state.tool_steps
            if step.round_id == round_id and step.status == ToolStepStatus.PLANNED
        ]

    def _existing_plan_round(self) -> RoundRecord | None:
        latest_round = self.state.latest_round()
        if latest_round is None:
            return None
        if latest_round.status == RoundStatus.THINKING:
            return None
        if self.state.list_tool_steps(latest_round.round_id):
            return latest_round
        if self.state.list_messages(latest_round.round_id):
            return latest_round
        return None

    def _existing_clarification_round(self, question: str) -> RoundRecord | None:
        latest_round = self.state.latest_round()
        if latest_round is None or latest_round.status != RoundStatus.AWAITING_AGENT:
            return None
        messages = self.state.list_messages(latest_round.round_id)
        if not messages:
            return None
        latest_message = messages[-1]
        if latest_message.kind != CollaborationMessageKind.QUESTION:
            return None
        if latest_message.content != question:
            return None
        if self.state.status != WorkflowStatus.CLARIFYING:
            return None
        return latest_round

    def _ensure_planning_ready(self) -> None:
        report = self.state.current_investigation_report()
        if report is None:
            raise ValueError("planning requires an investigation report")
        if report.ready_for_planning:
            return
        next_action = report.recommended_next_action.value
        blockers = ", ".join(report.inputs_missing or report.blocked_reasons) or "investigation incomplete"
        raise ValueError(f"planning is not ready; next_action={next_action}; blockers={blockers}")

    def _existing_thinking_round(self) -> RoundRecord | None:
        latest_round = self.state.latest_round()
        if latest_round is None or latest_round.status != RoundStatus.THINKING:
            return None
        if self.state.status != WorkflowStatus.THINKING:
            return None
        return latest_round

    def _activate_planning_round(self, owner: str, objective: str) -> RoundRecord:
        current_round = self.state.current_round()
        if current_round is not None and current_round.status == RoundStatus.THINKING:
            current_round.objective = objective
            current_round.set_status(RoundStatus.PLANNING)
            self.state.set_status(WorkflowStatus.PLANNING)
            self.state.touch()
            return current_round
        return self.start_round(owner, objective)
