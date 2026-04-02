"""Workflow execution mode enums.

Defines 4 execution modes, supporting from simple tool calls to multi-agent collaboration.
"""

from enum import Enum


class ExecutionMode(str, Enum):
    """Workflow Step execution modes."""
    
    TOOL = "tool"
    """Tool mode: one-time call, returns result immediately.
    
    Use case: Simple operations like file I/O, API calls.
    Execution: Call existing skill, return immediately.
    """
    
    AGENT = "agent"
    """Agent mode: Continuously running agent.
    
    Use case: Tasks requiring multi-turn reasoning or decision making.
    Execution: spawn → invoke → kill.
    """
    
    MULTI_AGENT = "multi_agent"
    """Multi-agent mode: Execute multiple agents in parallel.
    
    Use case: Parallelizable subtasks.
    Execution: Spawn N agents → execute in parallel → aggregate results.
    """
    
    DISCUSSION = "discussion"
    """Discussion mode: Multiple agents discuss until consensus.
    
    Use case: Reaching agreement among multiple parties.
    Execution: Create discussion thread → multi-round messages → convergence check.
    """


class StepStatus(str, Enum):
    """Step execution statuses."""

    PENDING = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class WorkflowStatus(str, Enum):
    """Workflow execution statuses."""
    
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
