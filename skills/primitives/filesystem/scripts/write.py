#!/usr/bin/env python3
"""Filesystem write - write content to file.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sys
from pathlib import Path

from common.path_utils import ensure_in_workspace as _ensure_in_workspace


def _normalize_path(path: str, workspace_root: Path) -> str:
    """Strip redundant workspace/ prefix; path is already relative to workspace."""
    p = path.strip().replace("\\", "/")
    prefixes = ("workspace/", "./workspace/")
    for prefix in prefixes:
        if p.lower().startswith(prefix.lower()):
            p = p[len(prefix):].lstrip("/")
            break
    return p or "."


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    workspace_root = Path(params.get("workspace_root", ""))
    path = params.get("path", "")
    content = params.get("content", "")

    if not path:
        print(json.dumps({"error": "path is required"}))
        return

    path = _normalize_path(path, workspace_root)
    target = workspace_root / path
    if not _ensure_in_workspace(workspace_root, target):
        print(json.dumps({"error": "Path cannot escape workspace"}))
        return

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", errors="replace")
        print(json.dumps({"success": True, "path": path}))
    except Exception as e:
        print(json.dumps({"error": f"Write failed: {str(e)}"}))


if __name__ == "__main__":
    main()
