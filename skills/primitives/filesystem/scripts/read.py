#!/usr/bin/env python3
"""Filesystem read - read file content."""
import json
import re
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
    offset = int(params.get("offset", 0))
    limit = int(params.get("limit", 0))
    tail = int(params.get("tail", 0))
    encoding = params.get("encoding", "utf-8")
    regex_str = params.get("regex", "")

    if not path:
        print(json.dumps({"error": "path is required"}))
        return
    fp = workspace_root / path
    if not fp.exists() or not fp.is_file():
        print(json.dumps({"error": f"File not found: {path}"}))
        return
    if not _ensure_in_workspace(workspace_root, fp):
        print(json.dumps({"error": "Path cannot escape workspace"}))
        return

    try:
        content = fp.read_text(encoding=encoding, errors="ignore")
    except Exception as e:
        print(json.dumps({"error": f"Read failed: {str(e)}"}))
        return

    lines = content.splitlines()
    total_lines = len(lines)

    if regex_str:
        try:
            pattern = re.compile(regex_str)
            lines = [line for line in lines if pattern.search(line)]
        except re.error as e:
            print(json.dumps({"error": f"Invalid regex: {str(e)}"}))
            return

    if tail > 0:
        lines = lines[-tail:]
    else:
        if offset > 0:
            lines = lines[offset:]
        if limit > 0:
            lines = lines[:limit]

    print(json.dumps({
        "path": path,
        "total_lines": total_lines,
        "displayed_lines": len(lines),
        "content": "\n".join(lines),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
