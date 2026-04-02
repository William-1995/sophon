#!/usr/bin/env python3
"""Read Sophon docs or skill README files.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""

import json
import sys
from pathlib import Path

from common.path_utils import ensure_in_workspace, resolve_sophon_root


def _normalize_kind(raw: object) -> str:
    kind = str(raw or "doc").strip().lower()
    if kind in {"doc", "docs", "document"}:
        return "doc"
    if kind == "skill":
        return "skill"
    if kind == "list":
        return "list"
    return "doc"


def _list_docs(docs_dir: Path) -> list[str]:
    return sorted(p.name for p in docs_dir.iterdir() if p.is_file())


def _list_skills(sophon_root: Path) -> list[str]:
    try:
        from core.skill_loader import get_skill_loader

        loader = get_skill_loader(sophon_root)
        index = loader.load_index()
        return sorted(entry["name"] for entry in index.values())
    except Exception:
        return []


def _resolve_doc_target(docs_dir: Path, name: str) -> Path | None:
    candidate = name.strip()
    if not candidate:
        return None
    if candidate.lower().startswith("docs/"):
        candidate = candidate.split("/", 1)[1]
    if "/" in candidate:
        target = (docs_dir / candidate).resolve()
    else:
        target = (docs_dir / (candidate if Path(candidate).suffix else f"{candidate}.md")).resolve()
    if not target.exists() or not target.is_file():
        return None
    if not ensure_in_workspace(docs_dir.parent, target):
        return None
    try:
        target.relative_to(docs_dir.resolve())
    except ValueError:
        return None
    return target


def _resolve_skill_target(sophon_root: Path, skill_name: str) -> Path | None:
    if not skill_name.strip():
        return None
    from core.skill_loader import get_skill_loader

    loader = get_skill_loader(sophon_root)
    skill = loader.get_skill(skill_name.strip())
    if not skill:
        return None
    skill_dir = Path(skill.get("dir", ""))
    if not skill_dir.exists():
        return None
    for candidate_name in ("README.md", "SKILL.md"):
        candidate = skill_dir / candidate_name
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def main() -> None:
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    kind = _normalize_kind(args.get("kind") or args.get("target_kind") or args.get("mode"))
    name = (args.get("name") or args.get("doc") or args.get("doc_name") or args.get("skill_name") or args.get("skill") or "").strip()

    sophon_root = resolve_sophon_root(params)
    if not sophon_root or not sophon_root.exists():
        print(json.dumps({"error": "Could not resolve Sophon project root"}))
        return

    docs_dir = sophon_root / "docs"
    if not docs_dir.exists() or not docs_dir.is_dir():
        print(json.dumps({"error": "docs directory not found"}))
        return

    if kind == "list":
        docs = _list_docs(docs_dir)
        skills = _list_skills(sophon_root)
        print(json.dumps({
            "docs": docs,
            "skills": skills,
            "observation": f"Available docs: {', '.join(docs)}; skills: {', '.join(skills)}",
        }, ensure_ascii=False))
        return

    if kind == "skill":
        if not name:
            skills = _list_skills(sophon_root)
            print(json.dumps({
                "skills": skills,
                "observation": f"Available skills: {', '.join(skills)}",
            }, ensure_ascii=False))
            return
        target = _resolve_skill_target(sophon_root, name)
        if not target:
            print(json.dumps({"error": f"Skill README not found: {name}"}))
            return
        content = target.read_text(encoding="utf-8", errors="replace")
        print(json.dumps({
            "kind": "skill",
            "name": name,
            "path": str(target),
            "content": content,
            "observation": f"Read {target.name} for skill {name} ({len(content)} chars)",
        }, ensure_ascii=False))
        return

    if not name:
        docs = _list_docs(docs_dir)
        print(json.dumps({
            "docs": docs,
            "observation": f"Available docs: {', '.join(docs)}",
        }, ensure_ascii=False))
        return

    target = _resolve_doc_target(docs_dir, name)
    if not target:
        print(json.dumps({"error": f"Doc not found: {name}"}))
        return
    content = target.read_text(encoding="utf-8", errors="replace")
    print(json.dumps({
        "kind": "doc",
        "name": name,
        "path": str(target),
        "content": content,
        "observation": f"Read {target.name} ({len(content)} chars)",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
