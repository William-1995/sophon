"""Skill catalog for the UI (names and descriptions from ``SKILL.md`` briefs)."""

from fastapi import APIRouter

from services.skills import list_skills

router = APIRouter(tags=["skills"])


@router.get("/api/skills")
def get_skills() -> dict:
    """List discoverable skills exposed to the frontend.

    Returns:
        Dict with ``skills`` list of ``name`` / ``description`` entries.
    """
    return list_skills()
