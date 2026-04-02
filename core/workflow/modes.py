"""Enums and transition rules for workflow collaboration."""

from __future__ import annotations

from enum import Enum


class CollaborationMessageKind(str, Enum):
    THOUGHT = "thought"
    QUESTION = "question"
    ANSWER = "answer"
    DECISION = "decision"
    FINAL = "final"
    TOOL_REQUEST = "tool_request"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"

    @property
    def category(self) -> str:
        return "execution" if self in EXECUTION_MESSAGE_KINDS else "collaboration"


class RoundStatus(str, Enum):
    THINKING = "thinking"
    PLANNING = "planning"
    AWAITING_TOOL = "awaiting_tool"
    AWAITING_AGENT = "awaiting_agent"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class WorkflowStatus(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    CLARIFYING = "clarifying"
    PLANNING = "planning"
    EXECUTING = "executing"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class InvestigationNextAction(str, Enum):
    INVESTIGATE_MORE = "investigate_more"
    CLARIFY = "clarify"
    PLAN = "plan"


class ToolStepStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


COLLABORATION_MESSAGE_KINDS = {
    CollaborationMessageKind.THOUGHT,
    CollaborationMessageKind.QUESTION,
    CollaborationMessageKind.ANSWER,
    CollaborationMessageKind.DECISION,
    CollaborationMessageKind.FINAL,
}

EXECUTION_MESSAGE_KINDS = {
    CollaborationMessageKind.TOOL_REQUEST,
    CollaborationMessageKind.TOOL_START,
    CollaborationMessageKind.TOOL_RESULT,
    CollaborationMessageKind.TOOL_ERROR,
}

ROUND_TRANSITIONS: dict[RoundStatus, set[RoundStatus]] = {
    RoundStatus.THINKING: {
        RoundStatus.PLANNING,
        RoundStatus.AWAITING_TOOL,
        RoundStatus.AWAITING_AGENT,
        RoundStatus.BLOCKED,
        RoundStatus.COMPLETED,
    },
    RoundStatus.PLANNING: {
        RoundStatus.AWAITING_TOOL,
        RoundStatus.AWAITING_AGENT,
        RoundStatus.SYNTHESIZING,
        RoundStatus.BLOCKED,
        RoundStatus.COMPLETED,
    },
    RoundStatus.AWAITING_TOOL: {
        RoundStatus.AWAITING_AGENT,
        RoundStatus.SYNTHESIZING,
        RoundStatus.BLOCKED,
        RoundStatus.COMPLETED,
    },
    RoundStatus.AWAITING_AGENT: {
        RoundStatus.PLANNING,
        RoundStatus.SYNTHESIZING,
        RoundStatus.BLOCKED,
        RoundStatus.COMPLETED,
    },
    RoundStatus.SYNTHESIZING: {RoundStatus.COMPLETED, RoundStatus.BLOCKED},
    RoundStatus.COMPLETED: set(),
    RoundStatus.BLOCKED: set(),
}

WORKFLOW_TRANSITIONS: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.IDLE: {
        WorkflowStatus.THINKING,
        WorkflowStatus.CLARIFYING,
        WorkflowStatus.PLANNING,
        WorkflowStatus.BLOCKED,
        WorkflowStatus.FAILED,
    },
    WorkflowStatus.THINKING: {
        WorkflowStatus.CLARIFYING,
        WorkflowStatus.PLANNING,
        WorkflowStatus.EXECUTING,
        WorkflowStatus.BLOCKED,
        WorkflowStatus.FAILED,
    },
    WorkflowStatus.CLARIFYING: {
        WorkflowStatus.THINKING,
        WorkflowStatus.PLANNING,
        WorkflowStatus.BLOCKED,
        WorkflowStatus.FAILED,
    },
    WorkflowStatus.PLANNING: {
        WorkflowStatus.THINKING,
        WorkflowStatus.CLARIFYING,
        WorkflowStatus.EXECUTING,
        WorkflowStatus.BLOCKED,
        WorkflowStatus.FAILED,
    },
    WorkflowStatus.EXECUTING: {
        WorkflowStatus.THINKING,
        WorkflowStatus.CLARIFYING,
        WorkflowStatus.SYNTHESIZING,
        WorkflowStatus.COMPLETED,
        WorkflowStatus.BLOCKED,
        WorkflowStatus.FAILED,
    },
    WorkflowStatus.SYNTHESIZING: {WorkflowStatus.COMPLETED, WorkflowStatus.BLOCKED, WorkflowStatus.FAILED},
    WorkflowStatus.COMPLETED: set(),
    WorkflowStatus.BLOCKED: set(),
    WorkflowStatus.FAILED: set(),
}

TOOL_STEP_TRANSITIONS: dict[ToolStepStatus, set[ToolStepStatus]] = {
    ToolStepStatus.PLANNED: {ToolStepStatus.RUNNING, ToolStepStatus.SKIPPED, ToolStepStatus.FAILED},
    ToolStepStatus.RUNNING: {ToolStepStatus.COMPLETED, ToolStepStatus.FAILED},
    ToolStepStatus.COMPLETED: set(),
    ToolStepStatus.FAILED: set(),
    ToolStepStatus.SKIPPED: set(),
}


def can_transition_round(current: RoundStatus, next_status: RoundStatus) -> bool:
    return next_status in ROUND_TRANSITIONS.get(current, set())


def can_transition_workflow(current: WorkflowStatus, next_status: WorkflowStatus) -> bool:
    return next_status in WORKFLOW_TRANSITIONS.get(current, set())


def can_transition_tool(current: ToolStepStatus, next_status: ToolStepStatus) -> bool:
    return next_status in TOOL_STEP_TRANSITIONS.get(current, set())
