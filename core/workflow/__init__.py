"""Workflow collaboration protocol (compatibility / experiment layer).

The main runtime execution path lives in `core.cowork.workflow.engine`. This
package keeps the investigate-first collaboration model available for explicit
use and compatibility with earlier workflow concepts.
"""

from .modes import (
    CollaborationMessageKind,
    InvestigationNextAction,
    RoundStatus,
    ToolStepStatus,
    WorkflowStatus,
)
from .orchestrator import PlannedToolStep, WorkflowOrchestrator
from .prompt import WORKFLOW_ORCHESTRATION_PROMPT, build_workflow_orchestration_prompt
from .records import InvestigationReport
from .state import MessageRecord, RoundRecord, ToolStepRecord, WorkflowState
from .store import WorkflowStore, workflow_store

__all__ = [
    "CollaborationMessageKind",
    "InvestigationNextAction",
    "InvestigationReport",
    "MessageRecord",
    "PlannedToolStep",
    "RoundRecord",
    "RoundStatus",
    "ToolStepRecord",
    "ToolStepStatus",
    "WorkflowOrchestrator",
    "build_workflow_orchestration_prompt",
    "WorkflowStore",
    "WorkflowState",
    "WorkflowStatus",
    "WORKFLOW_ORCHESTRATION_PROMPT",
    "workflow_store",
]
