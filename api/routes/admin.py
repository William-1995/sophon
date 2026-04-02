"""Administrative maintenance endpoints (database search index, etc.)."""

from fastapi import APIRouter

from services.admin import rebuild_memory_fts_endpoint

router = APIRouter(tags=["admin"])


@router.post("/api/admin/rebuild-memory-fts")
def post_rebuild_memory_fts() -> dict:
    """Rebuild the FTS5 index over long-term memory for search quality.

    Returns:
        Status dict confirming the rebuild ran.
    """
    return rebuild_memory_fts_endpoint()
