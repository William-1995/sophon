"""Admin-only maintenance (e.g. rebuilding memory FTS)."""

from db.schema import rebuild_memory_fts
from common.utils import get_db_path


def rebuild_memory_fts_endpoint() -> dict:
    """Rebuild the FTS5 virtual table over ``memory_long_term`` content.

    Intended after bulk DB imports so memory search stays consistent.

    Returns:
        Dict with ``status`` (``ok``) and human-readable ``message``.
    """
    db_path = get_db_path()
    rebuild_memory_fts(db_path)
    return {
        "status": "ok",
        "message": "Memory FTS5 index rebuilt",
    }
