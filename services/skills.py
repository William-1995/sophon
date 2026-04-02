"""Expose discoverable skills to the UI via ``core.skill_loader``."""

from core.skill_loader import get_skills_brief


def list_skills() -> dict:
    """Return discoverable skills for the UI mode picker.

    Returns:
        Dict with ``skills`` list of ``name`` and ``description`` strings.
    """
    brief = get_skills_brief()
    return {
        "skills": [
            {"name": s["skill_name"], "description": s["skill_description"]}
            for s in brief
        ]
    }
