"""HTTP API for cowork workflows: plan from text, execute, poll, and SSE snapshots."""

import asyncio
import hashlib
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from core.cowork.workflow.engine import WorkflowEngine
from core.cowork.workflow.plan_from_text import WorkflowPlanError, plan_workflow_steps_from_description
from core.cowork.workflow.state import WorkflowState as WfState
from services.workflows import list_workflow_instances


router = APIRouter(prefix="/api/workflows", tags=["workflows"])

_engine: Optional[WorkflowEngine] = None


def get_engine() -> WorkflowEngine:
    global _engine
    if _engine is None:
        _engine = WorkflowEngine()
    return _engine


def _step_sort_key(step_id: str) -> int:
    """Sort ``step_N`` ids numerically; unknown ids sort last."""
    if step_id.startswith("step_"):
        try:
            return int(step_id.split("_", 1)[1])
        except ValueError:
            pass
    return 10**9


def workflow_state_to_api_dict(state: WfState) -> Dict[str, Any]:
    """Serialize ``WorkflowState`` to the public JSON shape (REST + SSE)."""
    return {
        "workflow_id": state.workflow_id,
        "instance_id": state.instance_id,
        "status": state.status.value,
        "steps": {
            step_id: {
                "step_id": step.step_id,
                "name": step.name,
                "role": step.input_data.get("role"),
                "status": step.status.value,
                "output_data": step.output_data,
                "error_message": step.error_message,
                "execution_mode": step.execution_mode,
                "agent_id": step.agent_id,
                "agent_ids": step.agent_ids,
            }
            for step_id, step in state.steps.items()
        },
        "agents": {agent_id: agent.to_dict() for agent_id, agent in state.agents.items()},
        "messages": [msg.to_dict() for msg in state.messages],
        "threads": {thread_id: thread.to_dict() for thread_id, thread in state.threads.items()},
        "timeline": [event.to_dict() for event in state.timeline],
        "batch_progress": state.batch_progress,
        "current_step_id": state.current_step_id,
        "created_at": state.created_at,
        "started_at": state.started_at,
        "completed_at": state.completed_at,
        "error_message": state.error_message,
    }


def workflow_sse_signature(state: WfState) -> str:
    """Change when workflow status, active step, or any step output/status changes."""
    parts: List[str] = [state.status.value, state.current_step_id or ""]
    for sid in sorted(state.steps.keys(), key=_step_sort_key):
        st = state.steps[sid]
        parts.append(sid)
        parts.append(st.status.value)
        raw = json.dumps(st.output_data or {}, sort_keys=True, default=str)
        parts.append(hashlib.sha256(raw.encode()).hexdigest()[:24])
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


class CreateFromTextRequest(BaseModel):
    """Body for ``POST /api/workflows/create-from-text``."""

    description: str
    uploaded_files: list[str] | None = None


@router.post("/create-from-text")
async def create_workflow_from_text(request: CreateFromTextRequest):
    """Plan steps via LLM JSON, register a new instance, return ``instance_id``."""
    try:
        engine = get_engine()
        planned = await plan_workflow_steps_from_description(request.description, request.uploaded_files)
        steps = []
        for item in planned:
            steps.append(
                {
                    "role": item["role"],
                    "task": item["task"],
                    "skills": item.get("skills", []),
                }
            )
        instance_id = engine.create_instance(
            workflow_id="auto",
            steps=steps,
            input_data={
                "description": request.description,
                "uploaded_files": list(request.uploaded_files or []),
            },
        )
        return {"instance_id": instance_id}
    except WorkflowPlanError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_workflows():
    """Return workflow instance rows from ``workflow_instances`` (newest first)."""
    try:
        items = await list_workflow_instances()
        return {"instances": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/execute")
async def execute_workflow(instance_id: str, background_tasks: BackgroundTasks):
    """Execute a workflow instance."""
    try:
        engine = get_engine()
        state = engine.get_instance(instance_id)
        if not state:
            raise HTTPException(status_code=404, detail="Instance not found")

        background_tasks.add_task(engine.execute_instance, instance_id)
        return {"status": "started", "instance_id": instance_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}")
async def get_workflow_status(instance_id: str):
    """Return a full snapshot dict for one workflow instance."""
    try:
        engine = get_engine()
        state = engine.get_instance(instance_id)
        if not state:
            raise HTTPException(status_code=404, detail="Instance not found")

        return workflow_state_to_api_dict(state)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}/stream")
async def stream_workflow_status(instance_id: str):
    """Poll the engine once per second and emit JSON snapshots when state changes."""
    from fastapi.responses import StreamingResponse

    engine = get_engine()

    async def event_generator():
        last_sig: str | None = None

        while True:
            state = engine.get_instance(instance_id)

            if not state:
                yield f"data: {json.dumps({'error': 'Instance not found'})}\n\n"
                break

            sig = workflow_sse_signature(state)
            if sig != last_sig:
                last_sig = sig
                payload = workflow_state_to_api_dict(state)
                yield f"data: {json.dumps(payload)}\n\n"

            if state.status.value in ("completed", "failed"):
                break

            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
