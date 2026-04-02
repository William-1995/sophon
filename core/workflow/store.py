"""In-memory workflow store."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .orchestrator import WorkflowOrchestrator


@dataclass
class WorkflowStore:
    _workflows: dict[str, WorkflowOrchestrator] = field(default_factory=dict)

    def create(
        self,
        workflow_id: str,
        task: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowOrchestrator:
        orchestrator = WorkflowOrchestrator(workflow_id=workflow_id, task=task, metadata=metadata)
        self._workflows[workflow_id] = orchestrator
        return orchestrator

    def register(self, orchestrator: WorkflowOrchestrator) -> WorkflowOrchestrator:
        self._workflows[orchestrator.state.workflow_id] = orchestrator
        return orchestrator

    def get(self, workflow_id: str) -> WorkflowOrchestrator | None:
        return self._workflows.get(workflow_id)

    def list(self) -> list[dict[str, Any]]:
        return [orchestrator.state.snapshot() for orchestrator in self._workflows.values()]

    def snapshot(self, workflow_id: str) -> dict[str, Any] | None:
        orchestrator = self.get(workflow_id)
        if orchestrator is None:
            return None
        return orchestrator.state.snapshot()

    def clear(self) -> None:
        self._workflows.clear()


workflow_store = WorkflowStore()
