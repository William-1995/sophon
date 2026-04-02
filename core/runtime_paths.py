"""
Single place for Sophon repo root and skill-subprocess PYTHONPATH rules.

Skill scripts are launched with PYTHONPATH built here (see executor_subprocess.build_run_env);
they should not duplicate sys.path walks.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def sophon_project_root() -> Path:
    """Repo root: contains ``config/``, ``core/``, ``skills/`` (this file lives in ``core/``)."""
    return Path(__file__).resolve().parent.parent


def find_project_root_from_anchor(anchor: Path) -> Path:
    """Walk parents from a file or directory until ``config/`` + ``core/`` are found."""
    cur = anchor.resolve()
    if cur.is_file():
        cur = cur.parent
    for d in (cur, *cur.parents):
        if (d / "config").is_dir() and (d / "core").is_dir():
            return d
    raise RuntimeError(f"Cannot find Sophon project root (config/ + core/) from {anchor}")


def resolve_sophon_root_with_env() -> Path:
    """Prefer ``SOPHON_ROOT`` (subprocess); else anchored project root."""
    raw = (os.environ.get("SOPHON_ROOT") or "").strip()
    if raw:
        p = Path(raw).resolve()
        if p.is_dir():
            return p
    return sophon_project_root()


def skill_pythonpath_prefixes(script_path: Path) -> list[str]:
    """``.../<skill>/scripts/<action>.py`` → ``scripts/_lib``, ``<skill>/_lib``, ``scripts/``, skill dir."""
    p = script_path.resolve()
    scripts = p.parent
    if scripts.name != "scripts":
        return []
    skill = scripts.parent
    out: list[str] = []
    lib_in_scripts = scripts / "_lib"
    if lib_in_scripts.is_dir():
        out.append(str(lib_in_scripts))
    lib_in_skill = skill / "_lib"
    if lib_in_skill.is_dir():
        out.append(str(lib_in_skill))
    out.append(str(scripts))
    out.append(str(skill))
    return out


def build_skill_subprocess_pythonpath(project_root: Path, script_path: Path | None) -> str:
    """Ordered prefixes for skill subprocess: skill _lib + skill dir + primitives + repo."""
    parts: list[str] = []
    if script_path is not None:
        parts.extend(skill_pythonpath_prefixes(script_path))
    parts.append(str((project_root / "skills" / "primitives").resolve()))
    parts.append(str(project_root.resolve()))
    tail = os.environ.get("PYTHONPATH", "")
    if tail:
        parts.append(tail)
    return os.pathsep.join(parts)


def prepend_sys_path_once(paths: list[Path]) -> None:
    """Insert paths at front of ``sys.path`` if they exist and are not already present."""
    for p in paths:
        if not p.exists():
            continue
        s = str(p.resolve())
        if s not in sys.path:
            sys.path.insert(0, s)


def emotion_awareness_scripts_dir(project_root: Path | None = None) -> Path:
    """Directory containing emotion-awareness ``run.py`` helpers (``_lib`` imports)."""
    root = project_root or sophon_project_root()
    return (
        root
        / "skills"
        / "optional"
        / "entertainment"
        / "emotion-awareness"
        / "scripts"
    )
