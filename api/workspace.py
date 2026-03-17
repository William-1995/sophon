"""
Workspace API - Workspace file management.

List and query workspace files with recent files prioritization.
"""

from pathlib import Path

from db.recent_files import get_recent
from config import get_config


def list_workspace_files(q: str = "", recent_days: int = 7) -> dict:
    """List workspace files with recent files first.

    Args:
        q: Optional search query to filter files.
        recent_days: Number of days to consider as "recent".

    Returns:
        Dict with files list and recent files list.
    """
    cfg = get_config()
    ws = cfg.paths.user_workspace()
    db_path = cfg.paths.db_path()

    # Get recent files from DB
    recent = get_recent(db_path) if db_path.exists() else []

    if not ws.exists():
        return {"files": recent, "recent": recent}

    # Collect all files in workspace
    all_files = []
    for path in ws.rglob("*"):
        if path.is_file() and not path.name.startswith("."):
            rel = str(path.relative_to(ws))
            all_files.append(rel)

    # Apply search filter if provided
    if q:
        query_lower = q.lower()
        all_files = [f for f in all_files if query_lower in f.lower()]

    # Separate recent and other files
    recent_valid = [f for f in recent if f in all_files]
    rest = [f for f in sorted(all_files) if f not in recent_valid]

    # Limit total results
    max_results = 200
    remaining_slots = max_results - len(recent_valid)

    def _sanitize(s: str) -> str:
        return s.encode("utf-8", errors="replace").decode("utf-8")

    files_out = recent_valid + rest[:remaining_slots]
    return {
        "files": [_sanitize(f) for f in files_out],
        "recent": [_sanitize(f) for f in recent_valid],
    }


def get_profile_image_path() -> Path | None:
    """Return path to user profile image (me.jpeg) if it exists."""
    cfg = get_config()
    p = cfg.paths.profile_image_path()
    return p if p.exists() and p.is_file() else None


def get_sophon_image_path() -> Path | None:
    """Return path to Sophon avatar (sophon.jpeg) if it exists."""
    cfg = get_config()
    p = cfg.paths.sophon_image_path()
    return p if p.exists() and p.is_file() else None
