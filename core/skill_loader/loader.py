"""SkillLoader facade — cache, session briefs, singleton."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.runtime_paths import sophon_project_root
from .builtins import append_task_plan_to_brief, inject_task_plan_into_grouped
from .graph import briefs_from_load_order, compute_load_order, normalize_skill_key
from .grouping import build_grouped_list, default_internal_skills
from .scan import scan_skills_to_index

logger = logging.getLogger(__name__)

class SkillLoader:
    """Load and cache skills from SKILL.md files."""

    def __init__(self, root: Path | None = None):
        self._root = root or sophon_project_root()
        self._cache: dict[str, dict[str, Any]] = {}

    def load_index(self) -> dict[str, dict[str, Any]]:
        """Load all skills; result is cached per resolved root."""
        root_key = str(self._root.resolve())
        if root_key in self._cache:
            return self._cache[root_key]
        result = scan_skills_to_index(self._root)
        self._cache[root_key] = result
        return result

    def get_skills_brief(self, exposed_skills: set[str] | None = None) -> list[dict[str, str]]:
        index = self.load_index()
        if exposed_skills is None:
            try:
                from config import get_config

                exposed_skills = set(get_config().skills.exposed_skills)
            except Exception:
                exposed_skills = set()
        brief = [
            {"skill_name": d["name"], "skill_description": d["description"]}
            for d in index.values()
            if d.get("name") in exposed_skills
        ]
        append_task_plan_to_brief(brief, exposed_skills)
        return brief

    def get_skills_brief_grouped(self) -> list[dict[str, Any]]:
        index = self.load_index()
        result = build_grouped_list(index, internal=default_internal_skills())
        try:
            from config import get_config

            inject_task_plan_into_grouped(result, set(get_config().skills.exposed_skills))
        except Exception:
            pass
        return result

    def get_skills_for_session(
        self,
        skill_filter: str | None = None,
        selected_skills: list[str] | None = None,
    ) -> list[dict[str, str]]:
        index = self.load_index()
        raw_primaries = [skill_filter] if skill_filter else (selected_skills or [])
        from core.task_plan import REACT_BUILTIN_SKILL_NAMES, builtin_skill_brief

        primaries_keys: list[str] = []
        builtin_primaries: list[str] = []
        for p in raw_primaries:
            if p in REACT_BUILTIN_SKILL_NAMES:
                builtin_primaries.append(p)
                continue
            k = normalize_skill_key(p, index)
            if k is not None:
                primaries_keys.append(k)

        if not primaries_keys and not builtin_primaries:
            return []

        load_order = compute_load_order(primaries_keys, index) if primaries_keys else []
        logger.debug("load_order=%s builtins=%s", load_order, builtin_primaries)
        briefs = briefs_from_load_order(load_order, index)
        for bn in builtin_primaries:
            bb = builtin_skill_brief(bn)
            if bb and not any(x["skill_name"] == bb["skill_name"] for x in briefs):
                briefs.append(bb)
        return briefs

    def get_skill(self, skill_name: str) -> dict[str, Any] | None:
        index = self.load_index()
        key = normalize_skill_key(skill_name, index)
        if key is None:
            return None
        data = dict(index[key])
        skill_md = Path(data["skill_file_path"])
        if skill_md.exists():
            data["body"] = skill_md.read_text(encoding="utf-8")
        return data

    def get_skill_scripts(self, skill_name: str) -> list[Path]:
        data = self.get_skill(skill_name)
        if not data:
            return []
        skill_dir = Path(data["dir"])
        return [skill_dir / s for s in data.get("scripts", [])]


_shared_loader: SkillLoader | None = None


def get_skill_loader(root: Path | None = None) -> SkillLoader:
    global _shared_loader
    if _shared_loader is None:
        _shared_loader = SkillLoader(root)
    return _shared_loader


def get_skills_brief(root: Path | None = None) -> list[dict[str, str]]:
    return get_skill_loader(root).get_skills_brief()


def get_skills_brief_grouped(root: Path | None = None) -> list[dict[str, Any]]:
    return get_skill_loader(root).get_skills_brief_grouped()


def get_skills_for_session(
    skill_filter: str | None = None,
    selected_skills: list[str] | None = None,
    root: Path | None = None,
) -> list[dict[str, str]]:
    return get_skill_loader(root).get_skills_for_session(skill_filter, selected_skills)


def activate_skill(skill_name: str, root: Path | None = None) -> dict[str, Any] | None:
    return get_skill_loader(root).get_skill(skill_name)
