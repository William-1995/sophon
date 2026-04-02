#!/usr/bin/env python3
"""Filesystem info - get file/directory information.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sys
from datetime import datetime
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
    args = params.get("arguments") or params
    path = (args.get("path") or params.get("path") or ".").strip() or "."

    target = workspace_root / path
    if not target.exists():
        print(json.dumps({"error": f"Path not found: {path}"}))
        return
    if not _ensure_in_workspace(workspace_root, target):
        print(json.dumps({"error": "Path cannot escape workspace"}))
        return

    stat = target.stat()
    output = {
        "path": path,
        "type": "directory" if target.is_dir() else "file",
        "exists": True,
        "size": stat.st_size,
        "size_human": _human_size(stat.st_size) if target.is_file() else None,
        "created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "accessed": datetime.fromtimestamp(stat.st_atime).strftime("%Y-%m-%d %H:%M:%S"),
    }
    if target.is_file():
        output["extension"] = target.suffix

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
