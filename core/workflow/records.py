"""Workflow record types and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .modes import (
    CollaborationMessageKind,
    InvestigationNextAction,
    RoundStatus,
    ToolStepStatus,
    can_transition_round,
    can_transition_tool,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass
class MessageRecord:
    message_id: str
    kind: CollaborationMessageKind
    sender: str
    content: str
    round_id: str | None = None
    created_at: str = field(default_factory=_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def category(self) -> str:
        return self.kind.category

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "kind": self.kind.value,
            "category": self.category,
            "sender": self.sender,
            "content": self.content,
            "round_id": self.round_id,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


@dataclass
class InvestigationReport:
    intent: str
    constraints: list[str] = field(default_factory=list)
    inputs_found: list[str] = field(default_factory=list)
    inputs_missing: list[str] = field(default_factory=list)
    candidate_files: list[str] = field(default_factory=list)
    usable_tools: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    ready_for_planning: bool = False
    recommended_next_action: InvestigationNextAction = InvestigationNextAction.INVESTIGATE_MORE

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InvestigationReport":
        return cls(
            intent=data["intent"],
            constraints=list(data.get("constraints", [])),
            inputs_found=list(data.get("inputs_found", [])),
            inputs_missing=list(data.get("inputs_missing", [])),
            candidate_files=list(data.get("candidate_files", [])),
            usable_tools=list(data.get("usable_tools", [])),
            blocked_reasons=list(data.get("blocked_reasons", [])),
            ready_for_planning=bool(data.get("ready_for_planning", False)),
            recommended_next_action=InvestigationNextAction(
                data.get("recommended_next_action", InvestigationNextAction.INVESTIGATE_MORE.value)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "constraints": list(self.constraints),
            "inputs_found": list(self.inputs_found),
            "inputs_missing": list(self.inputs_missing),
            "candidate_files": list(self.candidate_files),
            "usable_tools": list(self.usable_tools),
            "blocked_reasons": list(self.blocked_reasons),
            "ready_for_planning": self.ready_for_planning,
            "recommended_next_action": self.recommended_next_action.value,
        }


@dataclass
class ToolStepRecord:
    step_id: str
    tool_name: str
    arguments: dict[str, Any]
    requested_by: str
    round_id: str
    status: ToolStepStatus = ToolStepStatus.PLANNED
    purpose: str = ""
    created_at: str = field(default_factory=_now)
    started_at: str | None = None
    finished_at: str | None = None
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        if self.status == ToolStepStatus.RUNNING:
            return
        if not can_transition_tool(self.status, ToolStepStatus.RUNNING):
            raise ValueError(f"invalid tool transition {self.status.value} -> running")
        self.status = ToolStepStatus.RUNNING
        self.started_at = _now()

    def complete(self, result: Any) -> None:
        if self.status == ToolStepStatus.COMPLETED:
            return
        if not can_transition_tool(self.status, ToolStepStatus.COMPLETED):
            raise ValueError(f"invalid tool transition {self.status.value} -> completed")
        self.status = ToolStepStatus.COMPLETED
        self.result = result
        self.finished_at = _now()

    def fail(self, error: str) -> None:
        if self.status == ToolStepStatus.FAILED:
            return
        if not can_transition_tool(self.status, ToolStepStatus.FAILED):
            raise ValueError(f"invalid tool transition {self.status.value} -> failed")
        self.status = ToolStepStatus.FAILED
        self.error = error
        self.finished_at = _now()

    def skip(self, reason: str = "") -> None:
        if self.status == ToolStepStatus.SKIPPED:
            return
        if not can_transition_tool(self.status, ToolStepStatus.SKIPPED):
            raise ValueError(f"invalid tool transition {self.status.value} -> skipped")
        self.status = ToolStepStatus.SKIPPED
        self.error = reason or self.error
        self.finished_at = _now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "tool_name": self.tool_name,
            "arguments": dict(self.arguments),
            "requested_by": self.requested_by,
            "round_id": self.round_id,
            "status": self.status.value,
            "purpose": self.purpose,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
            "metadata": dict(self.metadata),
        }


@dataclass
class RoundRecord:
    round_id: str
    index: int
    owner: str
    objective: str
    status: RoundStatus = RoundStatus.PLANNING
    message_ids: list[str] = field(default_factory=list)
    tool_step_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    summary: str = ""
    blocked_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = _now()

    def add_message(self, message_id: str) -> None:
        self.message_ids.append(message_id)
        self.touch()

    def add_tool_step(self, step_id: str) -> None:
        self.tool_step_ids.append(step_id)
        self.touch()

    def set_status(self, status: RoundStatus, reason: str = "", summary: str = "") -> None:
        if self.status == status:
            if reason:
                self.blocked_reason = reason
            if summary:
                self.summary = summary
            self.touch()
            return
        if not can_transition_round(self.status, status):
            raise ValueError(f"invalid round transition {self.status.value} -> {status.value}")
        self.status = status
        if reason:
            self.blocked_reason = reason
        if summary:
            self.summary = summary
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_id": self.round_id,
            "index": self.index,
            "owner": self.owner,
            "objective": self.objective,
            "status": self.status.value,
            "message_ids": list(self.message_ids),
            "tool_step_ids": list(self.tool_step_ids),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "summary": self.summary,
            "blocked_reason": self.blocked_reason,
            "metadata": dict(self.metadata),
        }
