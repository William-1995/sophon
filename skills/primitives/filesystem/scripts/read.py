#!/usr/bin/env python3
"""
Filesystem Read - Read file content from workspace.

Reads text files with support for:
- Line offset and limit (pagination)
- Tail reading (last N lines)
- Regex filtering
- Custom encodings

Security:
- Path traversal protection (ensures target is within workspace)
- Encoding error handling

Example:
    $ echo '{"path": "document.txt", "limit": 100}' | python read.py
    {"path": "document.txt", "total_lines": 500, "displayed_lines": 100, "content": "..."}
"""

import json
import re
import sys
from pathlib import Path

# Add skill root first (for constants), then project root
_skill_root = Path(__file__).resolve().parent.parent
_root = _skill_root.parent.parent.parent
for p in (_skill_root, _root):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from constants import DEFAULT_ENCODING


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_OFFSET = 0
DEFAULT_LIMIT = 0  # 0 means unlimited
DEFAULT_TAIL = 0   # 0 means disabled


# ---------------------------------------------------------------------------
# Private API
# ---------------------------------------------------------------------------

def _ensure_in_workspace(workspace_root: Path, target: Path) -> bool:
    """Check if target path is within workspace directory.

    Prevents directory traversal attacks by ensuring the resolved target
    is a subpath of the resolved workspace root.

    Args:
        workspace_root: Root directory of the workspace.
        target: File path to check.

    Returns:
        True if target is within workspace, False otherwise.
    """
    try:
        target.resolve().relative_to(workspace_root.resolve())
        return True
    except ValueError:
        return False


def _apply_filters(
    lines: list[str],
    regex_str: str | None,
    offset: int,
    limit: int,
    tail: int,
) -> tuple[list[str], int]:
    """Apply regex, offset, limit, and tail filters to lines.

    Args:
        lines: Original list of lines.
        regex_str: Optional regex pattern to filter lines.
        offset: Number of lines to skip from start.
        limit: Maximum number of lines to return (0 = unlimited).
        tail: Number of lines to return from end (overrides offset/limit).

    Returns:
        Tuple of (filtered lines, total original lines).
    """
    total_lines = len(lines)

    # Apply regex filter
    if regex_str:
        try:
            pattern = re.compile(regex_str)
            lines = [line for line in lines if pattern.search(line)]
        except re.error as e:
            raise ValueError(f"Invalid regex: {e}")

    # Apply tail filter (takes precedence)
    if tail > 0:
        lines = lines[-tail:]
    else:
        # Apply offset
        if offset > 0:
            lines = lines[offset:]
        # Apply limit
        if limit > 0:
            lines = lines[:limit]

    return lines, total_lines


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def main() -> None:
    """Main entry point for filesystem read operation.

    Reads parameters from stdin JSON, validates path security,
    reads file content, applies filters, and outputs result JSON.
    """
    # Parse input parameters
    params = json.loads(sys.stdin.read())

    # Extract parameters with defaults
    workspace_root = Path(params.get("workspace_root", ""))
    path = params.get("path", "")
    offset = int(params.get("offset", DEFAULT_OFFSET))
    limit = int(params.get("limit", DEFAULT_LIMIT))
    tail = int(params.get("tail", DEFAULT_TAIL))
    encoding = params.get("encoding", DEFAULT_ENCODING)
    regex_str = params.get("regex", "")

    # Validate required parameters
    if not path:
        print(json.dumps({"error": "path is required"}))
        return

    # Resolve target path
    target_path = workspace_root / path

    # Validate path exists
    if not target_path.exists() or not target_path.is_file():
        print(json.dumps({"error": f"File not found: {path}"}))
        return

    # Security check: prevent path traversal
    if not _ensure_in_workspace(workspace_root, target_path):
        print(json.dumps({"error": "Path cannot escape workspace"}))
        return

    # Read file content
    try:
        content = target_path.read_text(encoding=encoding, errors="ignore")
    except Exception as e:
        print(json.dumps({"error": f"Read failed: {e}"}))
        return

    # Split into lines and apply filters
    lines = content.splitlines()
    try:
        filtered_lines, total_lines = _apply_filters(
            lines, regex_str, offset, limit, tail
        )
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        return

    # Output result
    result = {
        "path": path,
        "total_lines": total_lines,
        "displayed_lines": len(filtered_lines),
        "content": "\n".join(filtered_lines),
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
