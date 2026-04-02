"""Which skills appear in round-1 selection vs internal-only merge."""

from __future__ import annotations

from dataclasses import dataclass

from .common import CAPABILITIES_SKILL_NAME


@dataclass(frozen=True)
class SkillConfig:
    """Skill exposure lists consumed by the skill loader and preparation layer.

    Attributes:
        exposed_skills (tuple[str, ...]): Names shown to the model/UI for selection.
        internal_skills (tuple[str, ...]): Merged after selection but not advertised
            as primary modes (e.g. empty by default).
    """

    exposed_skills: tuple[str, ...] = (
        "troubleshoot",
        "deep-research",
        "task_plan",
        "search",
        "crawler",
        "filesystem",
        "docs",
        "memory",
        "pdf",
        "excel",
        "word",
        CAPABILITIES_SKILL_NAME,
    )
    internal_skills: tuple[str, ...] = ()
