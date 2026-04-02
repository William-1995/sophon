"""Endpoints to cancel streaming runs and submit HITL decisions."""

from fastapi import APIRouter

from api.schemas.models import DecisionRequest
from services.state import request_cancel, submit_decision

router = APIRouter(tags=["runs"])


@router.post("/api/runs/{run_id}/cancel")
async def cancel_run_endpoint(run_id: str) -> dict:
    """Request cooperative cancellation for the given streaming ``run_id``.

    Args:
        run_id (str): Identifier emitted in ``RUN_STARTED`` for the stream.

    Returns:
        Acknowledgement dict with ``status`` and ``run_id``.
    """
    request_cancel(run_id)
    return {"status": "ok", "run_id": run_id}


@router.post("/api/runs/{run_id}/decision")
async def post_decision(run_id: str, req: DecisionRequest) -> dict:
    """Submit the user's choice for a pending ``DECISION_REQUIRED`` prompt.

    Args:
        run_id (str): Same run id as in the event payload.
        req (DecisionRequest): Body with ``choice`` (and optional ``choices``).

    Returns:
        Acknowledgement dict.
    """
    await submit_decision(run_id, req.choice)
    return {"status": "ok", "run_id": run_id}
