"""Memory scope helpers kept with the memory skill."""

from __future__ import annotations

from db import session_meta

from defaults import MEMORY_SCOPE_BY_PARENT
from common import resolve_db_path


def resolve_scoped_session_ids(params: dict, session_id: str | None) -> list[str] | None:
    if not MEMORY_SCOPE_BY_PARENT:
        return None
    db_path = resolve_db_path(params)
    if not db_path.exists() or not session_id:
        return None
    root_id = session_meta.get_root_session_id(db_path, session_id)
    return session_meta.get_session_ids_in_tree(db_path, root_id)
