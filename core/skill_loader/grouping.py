"""Group index entries by tier/channel for capabilities UI."""

from __future__ import annotations

from typing import Any
from constants import CAPABILITIES_SKILL_NAME


def default_internal_skills() -> set[str]:
    try:
        from config import get_config

        return set(get_config().skills.internal_skills)
    except Exception:
        return {CAPABILITIES_SKILL_NAME}


def build_grouped_list(
    index: dict[str, dict[str, Any]],
    *,
    internal: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return skills grouped by (tier, channel), ordered for display."""
    internal = internal if internal is not None else default_internal_skills()
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    tier_order = ["primitives", "feature", "tools", "optional"]

    for entry in index.values():
        if entry.get("name") in internal:
            continue
        tier = entry.get("tier", "primitives")
        channel = entry.get("channel", "")
        key = (tier, channel)
        groups.setdefault(key, []).append({
            "skill_name": entry["name"],
            "skill_description": entry["description"],
        })

    result: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for tier in tier_order:
        for key in sorted(groups.keys()):
            if key[0] != tier or key in seen_keys:
                continue
            seen_keys.add(key)
            result.append({"tier": key[0], "channel": key[1], "skills": groups[key]})
    for key in sorted(groups.keys()):
        if key not in seen_keys:
            result.append({"tier": key[0], "channel": key[1], "skills": groups[key]})
    return result
