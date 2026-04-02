#!/usr/bin/env python3
"""Filesystem count - count files and directories.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import fnmatch
import json
import sys
from pathlib import Path

from common.path_utils import ensure_in_workspace as _ensure_in_workspace


def _human_size(size_bytes: int | float) -> str:
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}TB"


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    workspace_root = Path(params.get("workspace_root", ""))
    path = params.get("path", "")
    pattern = params.get("pattern", "*")
    recursive = params.get("recursive", True)

    root = workspace_root / (path or ".") if path else workspace_root
    if not root.exists():
        print(json.dumps({"error": f"Path not found: {path or 'root'}"}))
        return
    if not root.is_dir():
        print(json.dumps({"error": f"Not a directory: {path}"}))
        return
    if not _ensure_in_workspace(workspace_root, root):
        print(json.dumps({"error": "Path cannot escape workspace"}))
        return

    total_files = 0
    total_dirs = 0
    total_size = 0

    if recursive:
        for item in root.rglob("*"):
            if item.is_file() and fnmatch.fnmatch(item.name, pattern):
                total_files += 1
                total_size += item.stat().st_size
            elif item.is_dir():
                total_dirs += 1
    else:
        for item in root.iterdir():
            if item.is_file() and fnmatch.fnmatch(item.name, pattern):
                total_files += 1
                total_size += item.stat().st_size
            elif item.is_dir():
                total_dirs += 1

    try:
        rel_path = str(root.relative_to(workspace_root)) if root != workspace_root else "."
    except ValueError:
        rel_path = "."
    output = {
        "path": rel_path,
        "pattern": pattern,
        "recursive": recursive,
        "files": total_files,
        "directories": total_dirs,
        "total_size": total_size,
        "total_size_human": _human_size(total_size),
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
