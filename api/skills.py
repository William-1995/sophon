"""
Skills API - Skill listing endpoint.

Provides skill information for the frontend.
"""

from core.skill_loader import get_skills_brief


def list_skills() -> dict:
    """Return skills for frontend.

    Returns:
        Dict with list of skills (name and description).
        Skill name corresponds to mode selection in UI.
    """
    brief = get_skills_brief()
    return {
        "skills": [
            {"name": s["skill_name"], "description": s["skill_description"]}
            for s in brief
        ]
    }
