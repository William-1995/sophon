"""
ReAct Context - Immutable context and mutable state for ReAct runs.

Provides strongly-typed containers for ReAct execution context and state,
following immutable/mutable separation principles.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ImmutableRunContext:
    """Immutable context for a ReAct run.

    Contains all configuration and initial state that does not change
    during the execution of a ReAct loop.

    Attributes:
        db: Path to the SQLite database.
        modified_question: User question with file injections applied.
        tools: List of OpenAI-format tool definitions available to the agent.
        system: System prompt for the LLM.
        messages: Current conversation messages (mutated in-place by rounds).
        start_round: Round number to start from (1 for new runs, >1 for resume).
        session_id: Session identifier for logging and tracing.
        user_id: User identifier.
        workspace_root: Root path for workspace operations.
        question: Original user question (before modifications).
    """

    db: Path
    modified_question: str
    tools: list
    system: str
    messages: list[dict[str, Any]]
    start_round: int
    session_id: str
    user_id: str
    workspace_root: Path
    question: str


@dataclass
class MutableRunState:
    """Mutable state accumulated during ReAct rounds.

    Contains all state that changes during execution, tracked across rounds.

    Attributes:
        total_tokens: Cumulative token count across all LLM calls.
        observations: List of observation strings from tool executions.
        all_references: List of reference dicts from tool executions.
        gen_ui_collected: Optional UI generation data from tools.
        answer_from_skill: Optional direct answer provided by a skill.
        cancelled: True if the run was cancelled by user request.
        resumable: True when checkpoint was saved (streaming cancel); False for HITL cancel.
    """

    total_tokens: int = 0
    observations: list[str] = field(default_factory=list)
    all_references: list[dict] = field(default_factory=list)
    gen_ui_collected: dict[str, Any] | None = None
    answer_from_skill: str | None = None
    cancelled: bool = False
    resumable: bool = False
