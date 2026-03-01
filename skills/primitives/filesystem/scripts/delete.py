#!/usr/bin/env python3
"""Filesystem delete - delete file(s)."""
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
    files = params.get("files", [])

    if not path and not files:
        print(json.dumps({"error": "path or files is required"}))
        return

    if path:
        files = [path] if isinstance(path, str) else ([path] if not isinstance(path, list) else path)
    if not isinstance(files, list):
        files = [files]

    results = []
    for f in files:
        if not isinstance(f, str):
            results.append({"path": str(f), "error": "Invalid path type"})
            continue
        target = workspace_root / f
        if not target.exists():
            results.append({"path": f, "error": f"File not found: {f}"})
            continue
        if not target.is_file():
            results.append({"path": f, "error": "Cannot delete directory, only files supported"})
            continue
        if not _ensure_in_workspace(workspace_root, target):
            results.append({"path": f, "error": "Path cannot escape workspace"})
            continue
        try:
            target.unlink()
            results.append({"path": f, "success": True})
        except Exception as e:
            results.append({"path": f, "error": f"Delete failed: {str(e)}"})

    all_success = all(r.get("success") for r in results)
    print(json.dumps({"success": all_success, "results": results}))


if __name__ == "__main__":
    main()
