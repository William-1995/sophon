"""
Path utilities for primitive skills.

Provides path resolution and manipulation utilities for file system operations
within workspace contexts.
"""

from pathlib import Path


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

DEFAULT_USER_ID = "default_user"
DEFAULT_WORKSPACE_ROOT = "."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_path(params: dict, file_path: str) -> Path:
    """Resolve file path relative to workspace.

    Handles:
    - Absolute paths (returned as-is)
    - Relative paths (resolved against workspace_root)
    - User ID stripping (if path starts with user_id)

    Args:
        params: Parameters dict containing workspace_root and optionally user_id.
        file_path: File path to resolve (absolute or relative).

    Returns:
        Resolved absolute Path.

    Example:
        >>> params = {
        ...     "workspace_root": "/workspace/user1",
        ...     "user_id": "user1"
        ... }
        >>> resolve_path(params, "documents/file.txt")
        PosixPath('/workspace/user1/documents/file.txt')
        
        >>> resolve_path(params, "user1/subdir/file.txt")
        PosixPath('/workspace/user1/subdir/file.txt')  # user1 prefix stripped
    """
    path = Path(file_path)
    
    # If already absolute, return as-is
    if path.is_absolute():
        return path
    
    # Get workspace root
    workspace_root = Path(params.get("workspace_root") or DEFAULT_WORKSPACE_ROOT).resolve()
    
    # Get user ID for prefix stripping
    user_id = str(params.get("user_id") or DEFAULT_USER_ID)
    
    # Strip user_id prefix if present
    if path.parts and path.parts[0] == user_id:
        if len(path.parts) > 1:
            path = Path(*path.parts[1:])
        else:
            path = Path(".")
    
    return workspace_root / path


def resolve_directory_path(params: dict, dir_path: str | None = None) -> Path:
    """Resolve directory path relative to workspace.

    Similar to resolve_path but specifically for directories.
    Empty or None dir_path resolves to workspace root.

    Args:
        params: Parameters dict containing workspace_root.
        dir_path: Directory path to resolve (optional).

    Returns:
        Resolved absolute Path to directory.
    """
    if not dir_path:
        return Path(params.get("workspace_root") or DEFAULT_WORKSPACE_ROOT).resolve()
    
    return resolve_path(params, dir_path)


def normalize_path(path: Path) -> str:
    """Convert path to normalized string representation.

    Args:
        path: Path to normalize.

    Returns:
        Normalized path string.
    """
    return str(path.resolve())


def get_file_extension(path: Path | str) -> str:
    """Get lowercase file extension without dot.

    Args:
        path: File path.

    Returns:
        Lowercase extension (e.g., 'txt', 'py') or empty string.
    """
    return Path(path).suffix.lower().lstrip(".")
