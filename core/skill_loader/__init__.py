"""
Skill loader package — SKILL.md discovery, DAG validation, session briefs.

Public API matches the former monolithic `core.skill_loader` module.
"""

from .loader import (
    SkillLoader,
    activate_skill,
    get_skill_loader,
    get_skills_brief,
    get_skills_brief_grouped,
    get_skills_for_session,
)

__all__ = [
    "SkillLoader",
    "activate_skill",
    "get_skill_loader",
    "get_skills_brief",
    "get_skills_brief_grouped",
    "get_skills_for_session",
]
