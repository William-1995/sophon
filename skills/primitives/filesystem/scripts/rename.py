#!/usr/bin/env python3
"""Filesystem rename - rename a file."""
import json
import sys
from pathlib import Path


def _ensure_in_workspace(workspace_root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(workspace_root.resolve())
        return True
    except ValueError:
        return False


def main() -> None:
    params = json.loads(sys.stdin.read())
    workspace_root = Path(params.get("workspace_root", ""))
    path = params.get("path", "")
    new_name = params.get("new_name", "")

    if not path or not new_name:
        print(json.dumps({"error": "path and new_name are required"}))
        return

    target = workspace_root / path
    if not target.exists():
        print(json.dumps({"error": f"File not found: {path}"}))
        return
    if not target.is_file():
        print(json.dumps({"error": "Cannot rename directory, only files supported"}))
        return
    if not _ensure_in_workspace(workspace_root, target):
        print(json.dumps({"error": "Path cannot escape workspace"}))
        return

    new_target = target.parent / new_name
    if not _ensure_in_workspace(workspace_root, new_target):
        print(json.dumps({"error": "Path cannot escape workspace"}))
        return

    try:
        target.rename(new_target)
        print(json.dumps({"success": True, "old_path": path, "new_path": new_name}))
    except Exception as e:
        print(json.dumps({"error": f"Rename failed: {str(e)}"}))


if __name__ == "__main__":
    main()
