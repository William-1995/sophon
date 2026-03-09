"""
Admin API - Administrative endpoints.

System maintenance and administrative operations.
"""

from db.schema import rebuild_memory_fts
from api.utils import get_db_path


def rebuild_memory_fts_endpoint() -> dict:
    """Rebuild FTS5 index from memory_long_term.

    Call after bulk imports to ensure search index is up to date.

    Returns:
        Status confirmation.
    """
    db_path = get_db_path()
    rebuild_memory_fts(db_path)
    return {
        "status": "ok",
        "message": "Memory FTS5 index rebuilt",
    }
