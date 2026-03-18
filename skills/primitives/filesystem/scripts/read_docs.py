#!/usr/bin/env python3
"""
Filesystem read_docs - Read Sophon project docs (setup, architecture, API).

Enables the LLM to answer setup/architecture questions by reading docs from
sophon/docs/ (e.g. SETUP.md, ARCHITECTURE.md, API.md, create-skill.md).

Example:
    $ echo '{"doc": "SETUP"}' | python read_docs.py
    {"doc": "SETUP", "content": "# Setup\n\n..."}
"""

import json
import os
import sys
from pathlib import Path

# Add skill root first, then project root
_skill_root = Path(__file__).resolve().parent.parent
_root = _skill_root.parent.parent.parent
for p in (_skill_root, _root):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _get_sophon_root(params: dict) -> Path:
    """Resolve Sophon project root from env, workspace path, or script location."""
    root = os.environ.get("SOPHON_ROOT")
    if root:
        return Path(root)
    ws = params.get("workspace_root", "")
    if ws:
        p = Path(ws).resolve()
        if "workspace" in p.parts:
            idx = list(p.parts).index("workspace")
            if idx > 0:
                return Path(*p.parts[:idx])
            return p.parent
        return p.parent.parent
    return _root


def main() -> None:
    """Read a doc from sophon/docs/ or list available docs."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    doc = (args.get("doc") or args.get("doc_name") or args.get("path") or "").strip()

    sophon_root = _get_sophon_root(params)
    if not sophon_root or not sophon_root.exists():
        print(json.dumps({"error": "Could not resolve Sophon project root"}))
        return

    docs_dir = sophon_root / "docs"
    if not docs_dir.exists() or not docs_dir.is_dir():
        print(json.dumps({"error": "docs directory not found"}))
        return

    if not doc or doc.lower() == "list":
        files = sorted(p.name for p in docs_dir.iterdir() if p.is_file())
        print(json.dumps({
            "docs": files,
            "observation": f"Available docs: {', '.join(files)}",
        }, ensure_ascii=False))
        return

    name = doc if "." in doc else f"{doc}.md"
    target = (docs_dir / name).resolve()
    if not target.is_relative_to(docs_dir.resolve()) or not target.exists():
        print(json.dumps({
            "doc": doc,
            "error": f"Doc not found: {name}. Use doc: \"list\" to see available docs.",
        }))
        return

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(json.dumps({"error": f"Failed to read doc: {e}"}))
        return

    result = {
        "doc": doc,
        "content": content,
        "observation": f"Read {target.name} ({len(content)} chars)",
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
