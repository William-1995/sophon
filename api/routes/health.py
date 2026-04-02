"""Liveness endpoint for load balancers and quick sanity checks."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict:
    """Return a minimal JSON body indicating the API process is up.

    Returns:
        Dict with ``status`` key ``ok``.
    """
    return {"status": "ok"}
