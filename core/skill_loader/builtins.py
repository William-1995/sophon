"""Merge built-in ReAct tools (e.g. task_plan) into brief/grouped lists."""

from __future__ import annotations

from typing import Any


def _exposed_skills() -> set[str]:
    try:
        from config import get_config

        return set(get_config().skills.exposed_skills)
    except Exception:
        return set()


def append_task_plan_to_brief(brief: list[dict[str, str]], exposed: set[str] | None) -> None:
    """Mutate brief: add task_plan row when it is exposed and not already present."""
    exposed = exposed if exposed is not None else _exposed_skills()
    from core.task_plan import TASK_PLAN_SKILL_NAME, builtin_skill_brief

    if TASK_PLAN_SKILL_NAME not in exposed:
        return
    bb = builtin_skill_brief(TASK_PLAN_SKILL_NAME)
    if bb and not any(b["skill_name"] == TASK_PLAN_SKILL_NAME for b in brief):
        brief.append(bb)


def inject_task_plan_into_grouped(result: list[dict[str, Any]], exposed: set[str]) -> None:
    """Mutate grouped list: append task_plan under primitives / empty channel when exposed."""
    from core.task_plan import TASK_PLAN_SKILL_NAME, builtin_skill_brief

    if TASK_PLAN_SKILL_NAME not in exposed:
        return
    bb = builtin_skill_brief(TASK_PLAN_SKILL_NAME)
    if not bb:
        return
    for g in result:
        if g.get("tier") == "primitives" and g.get("channel", "") == "":
            g.setdefault("skills", []).append(bb)
            return
    result.insert(0, {"tier": "primitives", "channel": "", "skills": [bb]})
