"""User workspace listing, uploads, zip download, and avatar path helpers."""

from __future__ import annotations

import io
import zipfile
import re
from pathlib import Path
from typing import Any

from db.recent_files import get_recent
from config import get_config
from constants import (
    API_WORKSPACE_DISPLAY_PARTS_MAX,
    API_WORKSPACE_UPLOAD_FILENAME_MAX_CHARS,
    WORKSPACE_UPLOAD_MAX_BYTES,
)

_SAFE_SUBDIR_PART = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
_HIDDEN_NAME_PREFIXES = (".",)
_HIDDEN_NAMES = {
    "sophon.db",
    "sophon.db-wal",
    "sophon.db-shm",
    "desktop.ini",
}
_IGNORED_DIR_NAMES = {
    "__pycache__",
    "node_modules",
    ".git",
}


def _is_visible_workspace_file(rel_path: str) -> bool:
    """Return whether a workspace-relative path is safe to expose in APIs.

    Args:
        rel_path (str): Path relative to the user workspace root.

    Returns:
        False for hidden segments, ignored dirs, SQLite sidecars, and common junk;
        True for normal visible files.
    """
    parts = [part for part in Path(rel_path).parts if part]
    if not parts:
        return False
    for part in parts:
        if part.startswith(_HIDDEN_NAME_PREFIXES) or part in _IGNORED_DIR_NAMES:
            return False
    name = parts[-1].lower()
    if name in _HIDDEN_NAMES:
        return False
    if name.endswith(".db") or name.endswith(".sqlite") or name.endswith(".sqlite3"):
        return False
    return True


def list_workspace_files(q: str = "", recent_days: int = 7) -> dict:
    """Merge recent-file hints from the DB with an on-disk scan of the workspace.

    Args:
        q (str): Optional case-insensitive substring filter.
        recent_days (int): Passed through for API symmetry (recent list source uses DB).

    Returns:
        ``files`` (merged ordering) and ``recent`` visible recent paths.
    """
    cfg = get_config()
    ws = cfg.paths.user_workspace()
    db_path = cfg.paths.db_path()

    # Get recent files from DB
    try:
        recent = get_recent(db_path) if db_path.exists() else []
    except Exception:
        recent = []

    visible_recent = [f for f in recent if _is_visible_workspace_file(f)]

    if not ws.exists():
        return {"files": visible_recent, "recent": visible_recent}

    # Collect all files in workspace
    all_files = []
    for path in ws.rglob("*"):
        if path.is_file():
            rel = str(path.relative_to(ws))
            if _is_visible_workspace_file(rel):
                all_files.append(rel)

    # Apply search filter if provided
    if q:
        query_lower = q.lower()
        all_files = [f for f in all_files if query_lower in f.lower()]

    # Separate recent and other files
    recent_valid = [f for f in visible_recent if f in all_files]
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
    """Resolve ``profile_image_path`` from config when the file is on disk.

    Returns:
        Absolute path or None.
    """
    cfg = get_config()
    p = cfg.paths.profile_image_path()
    return p if p.exists() and p.is_file() else None


def get_sophon_image_path() -> Path | None:
    """Resolve ``sophon_image_path`` from config when the file is on disk.

    Returns:
        Absolute path or None.
    """
    cfg = get_config()
    p = cfg.paths.sophon_image_path()
    return p if p.exists() and p.is_file() else None



def _safe_subdir(subdir: str) -> str:
    """Normalize upload subdir to safe segments under the workspace (default docs)."""
    raw = (subdir or "docs").strip().replace("\\", "/").strip("/")
    if not raw or ".." in raw:
        return "docs"
    parts = [p for p in raw.split("/") if p]
    safe: list[str] = []
    for p in parts[:API_WORKSPACE_DISPLAY_PARTS_MAX]:
        if not _SAFE_SUBDIR_PART.match(p):
            continue
        safe.append(p)
    return "/".join(safe) if safe else "docs"


def _safe_filename(name: str) -> str:
    """Strip path components and NULs; fall back to upload.bin when empty."""
    base = Path(name).name.replace("\x00", "")
    if not base or base in (".", ".."):
        return "upload.bin"
    return base[:API_WORKSPACE_UPLOAD_FILENAME_MAX_CHARS]


def _safe_download_name(name: str) -> str:
    """Ensure a .zip suffix and cap length for Content-Disposition."""
    base = Path(name).name.replace("\x00", "")
    if not base:
        return "workspace-files.zip"
    if not base.lower().endswith(".zip"):
        base = f"{base}.zip"
    return base[:API_WORKSPACE_UPLOAD_FILENAME_MAX_CHARS]


async def build_workspace_download_archive(
    files: list[str],
    archive_name: str = "workspace-files.zip",
) -> tuple[bytes, str]:
    """Zip visible, in-workspace files into memory.

    Args:
        files (list[str]): Relative paths; each must exist and pass visibility checks.
        archive_name (str): User-provided archive name (sanitized).

    Returns:
        Raw zip bytes and a safe download filename.

    Raises:
        ValueError: When no valid files remain after filtering.
    """
    cfg = get_config()
    ws = cfg.paths.user_workspace().resolve()
    cfg.paths.ensure_dirs()

    selected = []
    for raw in files:
        rel = str(raw or "").strip().replace('\\', '/')
        if not rel or not _is_visible_workspace_file(rel):
            continue
        candidate = (ws / rel).resolve()
        try:
            candidate.relative_to(ws)
        except ValueError:
            continue
        if candidate.exists() and candidate.is_file():
            selected.append((rel, candidate))

    if not selected:
        raise ValueError("no valid files selected")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel, candidate in selected:
            zf.write(candidate, arcname=rel)

    return buffer.getvalue(), _safe_download_name(archive_name)


def _normalize_uploads(uploads: Any) -> list[Any]:
    if uploads is None:
        return []
    if isinstance(uploads, list):
        return uploads
    if isinstance(uploads, tuple):
        return list(uploads)
    return [uploads]


async def save_workspace_uploads(
    uploads: Any,
    subdir: str = "docs",
) -> dict[str, Any]:
    """Persist multipart uploads under a safe subdirectory of the user workspace.

    Args:
        uploads (Any): One or more Starlette/FastAPI ``UploadFile`` objects (or compatible).
        subdir (str): Logical folder under the workspace (sanitized).

    Returns:
        Dict with ``saved`` relative paths and ``errors`` list of name/error dicts.
    """
    cfg = get_config()
    cfg.paths.ensure_dirs()
    ws = cfg.paths.user_workspace().resolve()
    rel_base = _safe_subdir(subdir)
    target = (ws / rel_base).resolve()
    try:
        target.relative_to(ws)
    except ValueError:
        target = (ws / "docs").resolve()
    target.mkdir(parents=True, exist_ok=True)

    saved: list[str] = []
    errors: list[dict[str, str]] = []

    for uf in _normalize_uploads(uploads):
        fname = getattr(uf, "filename", None) or "upload.bin"
        safe_name = _safe_filename(str(fname))
        dest = (target / safe_name).resolve()
        try:
            dest.relative_to(ws)
        except ValueError:
            errors.append({"name": safe_name, "error": "invalid path"})
            continue
        try:
            data = await uf.read()
        except Exception as e:  # noqa: BLE001
            errors.append({"name": safe_name, "error": str(e)})
            continue
        if len(data) > WORKSPACE_UPLOAD_MAX_BYTES:
            errors.append({"name": safe_name, "error": f"file too large (max {WORKSPACE_UPLOAD_MAX_BYTES} bytes)"})
            continue
        try:
            dest.write_bytes(data)
        except OSError as e:
            errors.append({"name": safe_name, "error": str(e)})
            continue
        saved.append(str(dest.relative_to(ws)))

    return {"saved": saved, "errors": errors}
