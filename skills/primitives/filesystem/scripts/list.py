#!/usr/bin/env python3
"""
Filesystem List - List files and directories in workspace.

Provides directory listing with:
- Recursive and non-recursive modes
- Pattern filtering (glob patterns)
- Sorting by name, size, or modification time
- Human-readable file sizes

Example:
    $ echo '{"path": ".", "recursive": true, "filter_pattern": "*.py"}' | python list.py
    {"path": ".", "summary": {...}, "files": [...], "directories": [...]}
"""

import fnmatch
import json
import sys
from pathlib import Path

# Add skill root first (for constants), then project root
_skill_root = Path(__file__).resolve().parent.parent
_root = _skill_root.parent.parent.parent
for p in (_skill_root, _root):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from constants import DEFAULT_QUERY_LIMIT


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

DEFAULT_SORT_BY = "name"
DEFAULT_ORDER = "asc"
MAX_FILES_DISPLAY = 200
MAX_DIRECTORIES_DISPLAY = 50

VALID_SORT_FIELDS = ["name", "size", "mtime"]
VALID_ORDERS = ["asc", "desc"]


# ---------------------------------------------------------------------------
# Private API
# ---------------------------------------------------------------------------

def _ensure_in_workspace(workspace_root: Path, target: Path) -> bool:
    """Check if target path is within workspace directory.

    Prevents directory traversal attacks.

    Args:
        workspace_root: Root directory of the workspace.
        target: Path to check.

    Returns:
        True if target is within workspace, False otherwise.
    """
    try:
        target.resolve().relative_to(workspace_root.resolve())
        return True
    except ValueError:
        return False


def _human_size(size_bytes: int | float) -> str:
    """Convert bytes to human-readable format.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Human-readable size string (e.g., "1.5KB", "2.3MB").
    """
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}TB"


def _matches_filter(item: Path, pattern: str) -> bool:
    """Check if item name matches glob pattern.

    Args:
        item: Path to check.
        pattern: Glob pattern (e.g., "*.py", "*.txt").

    Returns:
        True if matches or no pattern provided.
    """
    if not pattern:
        return True
    return fnmatch.fnmatch(item.name, pattern)


def _get_sort_key(sort_by: str):
    """Get sort key function for given field.

    Args:
        sort_by: Field name ("name", "size", "mtime").

    Returns:
        Key function for sorting.
    """
    sort_keys = {
        "name": lambda x: x.name.lower(),
        "size": lambda x: x.stat().st_size if x.is_file() else 0,
        "mtime": lambda x: x.stat().st_mtime,
    }
    return sort_keys.get(sort_by, sort_keys["name"])


def _collect_items(
    root: Path,
    recursive: bool,
    pattern: str,
) -> list[Path]:
    """Collect file system items from directory.

    Args:
        root: Root directory to scan.
        recursive: Whether to scan recursively.
        pattern: Optional glob pattern to filter.

    Returns:
        List of matching Path objects.
    """
    if recursive:
        items = [
            item for item in root.rglob("*")
            if _matches_filter(item, pattern)
        ]
    else:
        items = [
            item for item in root.iterdir()
            if _matches_filter(item, pattern)
        ]

    return items


def _build_output_item(item: Path, workspace_root: Path) -> dict:
    """Build output dict for a file system item.

    Args:
        item: Path object.
        workspace_root: Workspace root for relative path calculation.

    Returns:
        Dict with item details.
    """
    try:
        rel_path = item.relative_to(workspace_root)
    except ValueError:
        rel_path = Path(item.name)

    if item.is_file():
        size = item.stat().st_size
        return {
            "name": str(rel_path),
            "type": "file",
            "size": size,
            "size_display": _human_size(size),
        }
    else:
        return {
            "name": str(rel_path),
            "type": "dir",
            "size": 0,
            "size_display": "-",
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def main() -> None:
    """Main entry point for filesystem list operation."""
    # Parse input
    params = json.loads(sys.stdin.read())

    # Extract parameters with defaults
    workspace_root = Path(params.get("workspace_root", ""))
    path = params.get("path", ".")
    sort_by = params.get("sort_by", DEFAULT_SORT_BY)
    order = params.get("order", DEFAULT_ORDER)
    filter_pattern = params.get("filter_pattern", "")
    recursive = params.get("recursive", False)

    # Normalize empty path to root
    if not path or path == ".":
        path = ""

    # Resolve target path
    target_path = workspace_root / path if path else workspace_root

    # Validate path exists and is directory
    if not target_path.exists() or not target_path.is_dir():
        print(json.dumps({
            "error": f"Not found or not directory: {path or 'root'}"
        }))
        return

    # Security check
    if not _ensure_in_workspace(workspace_root, target_path):
        print(json.dumps({"error": "Path cannot escape workspace"}))
        return

    # Collect items
    items = _collect_items(target_path, recursive, filter_pattern)

    # Sort items
    sort_key = _get_sort_key(sort_by)
    reverse = order == "desc"
    items.sort(key=sort_key, reverse=reverse)

    # Build output
    files = []
    directories = []

    for item in items[:MAX_FILES_DISPLAY]:
        item_data = _build_output_item(item, workspace_root)
        if item.is_file():
            files.append(item_data)
        else:
            directories.append(item_data)

    # Prepare output
    output = {
        "path": path or ".",
        "summary": {
            "total_items": len(items),
            "files_count": len(files),
            "directories_count": len(directories),
        },
        "files": files,
        "directories": directories[:MAX_DIRECTORIES_DISPLAY],
    }

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
