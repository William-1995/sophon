"""Workflow aggregate state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .modes import CollaborationMessageKind, RoundStatus, WorkflowStatus, can_transition_workflow
from .records import InvestigationReport, MessageRecord, RoundRecord, ToolStepRecord, _new_id, _now


@dataclass
class WorkflowState:
    workflow_id: str
    task: str
    status: WorkflowStatus = WorkflowStatus.IDLE
    rounds: list[RoundRecord] = field(default_factory=list)
    messages: list[MessageRecord] = field(default_factory=list)
    tool_steps: list[ToolStepRecord] = field(default_factory=list)
    active_round_id: str | None = None
    final_summary: str = ""
    error: str = ""
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = _now()

    def _get_round(self, round_id: str) -> RoundRecord:
        for round_record in self.rounds:
            if round_record.round_id == round_id:
                return round_record
        raise KeyError(f"unknown round: {round_id}")

    def current_round(self) -> RoundRecord | None:
        return self._get_round(self.active_round_id) if self.active_round_id else None

    def current_investigation_report(self) -> InvestigationReport | None:
        round_record = self.current_round()
        if round_record is None:
            return None
        raw_report = round_record.metadata.get("investigation_report")
        if raw_report is None:
            return None
        return InvestigationReport.from_dict(raw_report)

    def latest_investigation_report(self) -> InvestigationReport | None:
        raw_report = self.metadata.get("investigation_report")
        if raw_report is None:
            return None
        return InvestigationReport.from_dict(raw_report)

    def get_round(self, round_id: str) -> RoundRecord:
        return self._get_round(round_id)

    def list_rounds(self) -> list[RoundRecord]:
        return list(self.rounds)

    def latest_round(self) -> RoundRecord | None:
        return self.rounds[-1] if self.rounds else None

    def list_messages(self, round_id: str | None = None) -> list[MessageRecord]:
        if round_id is None:
            return list(self.messages)
        return [message for message in self.messages if message.round_id == round_id]

    def thinking_messages(self, round_id: str | None = None) -> list[MessageRecord]:
        messages = self.list_messages(round_id)
        return [message for message in messages if message.kind == CollaborationMessageKind.THOUGHT]

    def list_tool_steps(self, round_id: str | None = None) -> list[ToolStepRecord]:
        if round_id is None:
            return list(self.tool_steps)
        return [step for step in self.tool_steps if step.round_id == round_id]

    def has_plan(self) -> bool:
        return bool(self.tool_steps or self.rounds)

    def begin_thinking(
        self,
        owner: str,
        objective: str,
        metadata: dict[str, Any] | None = None,
    ) -> RoundRecord:
        round_record = RoundRecord(
            round_id=_new_id("round"),
            index=len(self.rounds) + 1,
            owner=owner,
            objective=objective,
            status=RoundStatus.THINKING,
            metadata=dict(metadata or {}),
        )
        self.rounds.append(round_record)
        self.active_round_id = round_record.round_id
        self.set_status(WorkflowStatus.THINKING)
        self.metadata["thinking_round_id"] = round_record.round_id
        self.touch()
        return round_record

    def set_investigation_report(
        self,
        round_id: str,
        report: InvestigationReport,
    ) -> InvestigationReport:
        round_record = self._get_round(round_id)
        round_record.metadata["investigation_report"] = report.to_dict()
        self.metadata["investigation_report"] = report.to_dict()
        self.metadata["ready_for_planning"] = report.ready_for_planning
        self.metadata["recommended_next_action"] = report.recommended_next_action.value
        self.touch()
        return report

    def start_round(self, owner: str, objective: str, metadata: dict[str, Any] | None = None) -> RoundRecord:
        if self.status in {WorkflowStatus.IDLE, WorkflowStatus.CLARIFYING, WorkflowStatus.THINKING}:
            self.set_status(WorkflowStatus.PLANNING)
        round_record = RoundRecord(
            round_id=_new_id("round"),
            index=len(self.rounds) + 1,
            owner=owner,
            objective=objective,
            metadata=dict(metadata or {}),
        )
        self.rounds.append(round_record)
        self.active_round_id = round_record.round_id
        self.set_status(WorkflowStatus.PLANNING)
        self.touch()
        return round_record

    def add_message(
        self,
        kind: CollaborationMessageKind,
        sender: str,
        content: str,
        round_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MessageRecord:
        effective_round_id = round_id or self.active_round_id
        message = MessageRecord(
            message_id=_new_id("msg"),
            kind=kind,
            sender=sender,
            content=content,
            round_id=effective_round_id,
            metadata=dict(metadata or {}),
        )
        self.messages.append(message)
        if effective_round_id is not None:
            self._get_round(effective_round_id).add_message(message.message_id)
        self.touch()
        return message

    def add_tool_step(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        requested_by: str,
        round_id: str | None = None,
        purpose: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ToolStepRecord:
        effective_round_id = round_id or self.active_round_id
        if effective_round_id is None:
            raise ValueError("tool step requires an active round")
        step = ToolStepRecord(
            step_id=_new_id("step"),
            tool_name=tool_name,
            arguments=dict(arguments),
            requested_by=requested_by,
            round_id=effective_round_id,
            purpose=purpose,
            metadata=dict(metadata or {}),
        )
        self.tool_steps.append(step)
        self._get_round(effective_round_id).add_tool_step(step.step_id)
        self.touch()
        return step

    def set_round_status(self, round_id: str, status: RoundStatus, reason: str = "", summary: str = "") -> RoundRecord:
        round_record = self._get_round(round_id)
        round_record.set_status(status, reason=reason, summary=summary)
        self.touch()
        return round_record

    def complete_round(self, round_id: str, summary: str = "") -> RoundRecord:
        round_record = self.set_round_status(round_id, RoundStatus.COMPLETED, summary=summary)
        if self.active_round_id == round_id:
            self.active_round_id = None
        if round_record.summary and not self.final_summary:
            self.final_summary = round_record.summary
        self.touch()
        return round_record

    def block_round(self, round_id: str, reason: str) -> RoundRecord:
        return self.set_round_status(round_id, RoundStatus.BLOCKED, reason=reason)

    def require_clarification(
        self,
        owner: str,
        objective: str,
        question: str,
        *,
        sender: str = "orchestrator",
        metadata: dict[str, Any] | None = None,
    ) -> RoundRecord:
        round_record = self.current_round()
        if round_record is None or round_record.status != RoundStatus.THINKING:
            round_record = self.begin_thinking(owner, objective, metadata=metadata)
        round_record.set_status(RoundStatus.AWAITING_AGENT)
        self.set_status(WorkflowStatus.CLARIFYING)
        self.add_message(
            CollaborationMessageKind.QUESTION,
            sender,
            question,
            round_id=round_record.round_id,
            metadata=metadata,
        )
        self.metadata["awaiting_user_input"] = True
        self.metadata["clarification_round_id"] = round_record.round_id
        self.touch()
        return round_record

    def set_status(self, status: WorkflowStatus, error: str = "") -> None:
        if self.status == status:
            if error:
                self.error = error
            self.touch()
            return
        if not can_transition_workflow(self.status, status):
            raise ValueError(f"invalid workflow transition {self.status.value} -> {status.value}")
        self.status = status
        if error:
            self.error = error
        self.touch()

    def mark_completed(self, summary: str = "") -> None:
        self.final_summary = summary or self.final_summary
        self.set_status(WorkflowStatus.COMPLETED)

    def mark_failed(self, error: str) -> None:
        self.error = error
        self.set_status(WorkflowStatus.FAILED)

    def snapshot(self) -> dict[str, Any]:
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        investigation_report = self.latest_investigation_report()
        return {
            "workflow_id": self.workflow_id,
            "task": self.task,
            "status": self.status.value,
            "rounds": [round_record.to_dict() for round_record in self.rounds],
            "messages": [message.to_dict() for message in self.messages],
            "thinking_messages": [message.to_dict() for message in self.thinking_messages()],
            "tool_steps": [step.to_dict() for step in self.tool_steps],
            "active_round_id": self.active_round_id,
            "investigation_report": None if investigation_report is None else investigation_report.to_dict(),
            "ready_for_planning": self.metadata.get("ready_for_planning", False),
            "recommended_next_action": self.metadata.get("recommended_next_action"),
            "final_summary": self.final_summary,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }
