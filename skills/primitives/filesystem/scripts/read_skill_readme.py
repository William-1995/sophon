#!/usr/bin/env python3
"""
Filesystem read_skill_readme - Read a skill's README.md for installation and usage details.

Enables the LLM to guide users on setup (e.g. pip install, LibreOffice for .doc)
by reading each skill's README.md which documents capabilities, dependencies, and
platform-specific installation instructions.

Example:
    $ echo '{"skill_name": "word"}' | python read_skill_readme.py
    {"skill_name": "word", "content": "# Word Skill\n\nParse Word..."}
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
        return p.parent.parent  # workspace/user_id -> project
    return _root


def main() -> None:
    """Read a skill's README.md and return its content."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    skill_name = (args.get("skill_name") or args.get("skill") or "").strip()

    if not skill_name:
        print(json.dumps({"error": "skill_name is required"}))
        return

    sophon_root = _get_sophon_root(params)
    if not sophon_root or not sophon_root.exists():
        print(json.dumps({"error": "Could not resolve Sophon project root"}))
        return

    try:
        from core.skill_loader import get_skill_loader
        loader = get_skill_loader(sophon_root)
        skill = loader.get_skill(skill_name)
    except Exception as e:
        print(json.dumps({"error": f"Failed to load skill: {e}"}))
        return

    if not skill:
        print(json.dumps({"error": f"Unknown skill: {skill_name}"}))
        return

    skill_dir = Path(skill.get("dir", ""))
    if not skill_dir or not skill_dir.exists():
        print(json.dumps({"error": f"Skill directory not found: {skill_name}"}))
        return

    readme_path = skill_dir / "README.md"
    if not readme_path.exists() or not readme_path.is_file():
        print(json.dumps({
            "skill_name": skill_name,
            "content": None,
            "observation": f"Skill {skill_name} has no README.md",
        }))
        return

    try:
        content = readme_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(json.dumps({"error": f"Failed to read README: {e}"}))
        return

    result = {
        "skill_name": skill_name,
        "content": content,
        "observation": f"Read README.md for skill {skill_name} ({len(content)} chars)",
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
