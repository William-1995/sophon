"""Resolve workspace-relative paths for primitive skills."""

from pathlib import Path
import os

DEFAULT_USER_ID = "default_user"
DEFAULT_WORKSPACE_ROOT = "."


def resolve_workspace_root(params: dict) -> Path:
    """Resolve the active workspace root from skill params."""
    return Path(params.get("workspace_root") or DEFAULT_WORKSPACE_ROOT).resolve()


def resolve_sophon_root(params: dict) -> Path:
    """Resolve the Sophon project root from env, workspace, or runtime paths."""
    root = os.environ.get("SOPHON_ROOT")
    if root:
        return Path(root)
    ws = params.get("workspace_root", "")
    if ws:
        p = Path(ws).resolve()
        if "workspace" in p.parts:
            idx = list(p.parts).index("workspace")
            if idx > 0:
                return Path(*p.parts[:idx])
            return p.parent
        return p.parent.parent
    from core.runtime_paths import sophon_project_root

    return sophon_project_root()


def ensure_in_workspace(workspace_root: Path, target: Path) -> bool:
    """Return True when ``target`` resolves inside ``workspace_root``."""
    try:
        target.resolve().relative_to(workspace_root.resolve())
        return True
    except ValueError:
        return False


def resolve_path(params: dict, file_path: str) -> Path:
    """Resolve ``file_path`` against ``workspace_root`` in ``params``.

    Absolute paths are returned as-is. If the first path segment equals ``user_id``,
    that segment is stripped before joining to the workspace root.
    """
    path = Path(file_path)

    if path.is_absolute():
        return path

    workspace_root = resolve_workspace_root(params)
    user_id = str(params.get("user_id") or DEFAULT_USER_ID)

    if path.parts and path.parts[0] == user_id:
        if len(path.parts) > 1:
            path = Path(*path.parts[1:])
        else:
            path = Path(".")

    return workspace_root / path


def resolve_directory_path(params: dict, dir_path: str | None = None) -> Path:
    """Like ``resolve_path`` for directories; empty ``dir_path`` means workspace root."""
    if not dir_path:
        return resolve_workspace_root(params)

    return resolve_path(params, dir_path)


def normalize_path(path: Path) -> str:
    """Return ``path.resolve()`` as a string."""
    return str(path.resolve())


def get_file_extension(path: Path | str) -> str:
    """Lowercase suffix without leading dot."""
    return Path(path).suffix.lower().lstrip(".")
