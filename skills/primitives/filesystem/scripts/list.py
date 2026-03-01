#!/usr/bin/env python3
"""Filesystem list - list files in workspace."""
import fnmatch
import json
import sys
from pathlib import Path

MAX_FILES_DISPLAY = 200
MAX_DIRECTORIES_DISPLAY = 50


def _human_size(size_bytes: int | float) -> str:
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}TB"


def _ensure_in_workspace(workspace_root: Path, target: Path) -> bool:
    """Ensure target is within workspace (no path traversal)."""
    try:
        target.resolve().relative_to(workspace_root.resolve())
        return True
    except ValueError:
        return False


def main() -> None:
    params = json.loads(sys.stdin.read())
    workspace_root = Path(params.get("workspace_root", ""))
    path = params.get("path", ".")
    sort_by = params.get("sort_by", "name")
    order = params.get("order", "asc")
    filter_pattern = params.get("filter_pattern", "")
    recursive = params.get("recursive", False)

    if not path or path == ".":
        path = ""
    root = workspace_root / path if path else workspace_root
    if not root.exists() or not root.is_dir():
        print(json.dumps({"error": f"Not found or not directory: {path or 'root'}"}))
        return
    if not _ensure_in_workspace(workspace_root, root):
        print(json.dumps({"error": "Path cannot escape workspace"}))
        return

    items_raw: list[Path] = []
    if recursive:
        for item in root.rglob("*"):
            if filter_pattern and not fnmatch.fnmatch(item.name, filter_pattern):
                continue
            items_raw.append(item)
    else:
        for item in root.iterdir():
            if filter_pattern and not fnmatch.fnmatch(item.name, filter_pattern):
                continue
            items_raw.append(item)

    sort_key_map = {
        "name": lambda x: x.name.lower(),
        "size": lambda x: x.stat().st_size if x.is_file() else 0,
        "mtime": lambda x: x.stat().st_mtime,
    }
    sort_key = sort_key_map.get(sort_by, sort_key_map["name"])
    items_raw.sort(key=sort_key, reverse=(order == "desc"))

    files = []
    directories = []
    for item in items_raw[:MAX_FILES_DISPLAY]:
        try:
            rel = item.relative_to(workspace_root)
        except ValueError:
            rel = Path(item.name)
        if item.is_file():
            size = item.stat().st_size
            files.append({
                "name": str(rel),
                "type": "file",
                "size": size,
                "size_display": _human_size(size),
            })
        else:
            directories.append({
                "name": str(rel),
                "type": "dir",
                "size": 0,
                "size_display": "-",
            })

    output = {
        "path": path or ".",
        "summary": {
            "total_items": len(items_raw),
            "files_count": len(files),
            "directories_count": len(directories),
        },
        "files": files,
        "directories": directories[:MAX_DIRECTORIES_DISPLAY],
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
