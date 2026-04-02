"""Shared runtime capability resolution for chat and workflow.

This module keeps skill discovery/selection logic in one place so different
runtimes (chat, workflow) can apply the same capability model.
"""

from __future__ import annotations

from functools import lru_cache
import re
from typing import Any, Iterable

from config import get_config
from core.skill_loader.loader import get_skill_loader

_TOKEN_PATTERN = re.compile(r"[a-z0-9_+-]+", re.IGNORECASE)
_STOPWORDS = {
    "and",
    "for",
    "with",
    "the",
    "you",
    "your",
    "this",
    "that",
    "from",
    "into",
    "stage",
    "skill",
    "skills",
    "workflow",
    "agent",
}



def tokenize_text(value: str) -> set[str]:
    tokens = {t.lower() for t in _TOKEN_PATTERN.findall(value or "")}
    return {t for t in tokens if len(t) >= 3 and t not in _STOPWORDS}


@lru_cache(maxsize=1)
def runtime_skill_index() -> dict[str, dict[str, Any]]:
    try:
        return get_skill_loader().load_index()
    except Exception:
        return {}


@lru_cache(maxsize=1)
def internal_skill_names() -> set[str]:
    try:
        return set(get_config().skills.internal_skills or ())
    except Exception:
        return set()



def filter_runtime_skills(skill_names: Iterable[str], *, exclude_internal: bool = True) -> tuple[str, ...]:
    available = set(runtime_skill_index().keys())
    internal = internal_skill_names() if exclude_internal else set()
    normalized = tuple(str(skill).strip() for skill in skill_names if str(skill).strip())
    if not available:
        return tuple(skill for skill in normalized if skill not in internal)
    return tuple(
        skill
        for skill in normalized
        if skill in available and skill not in internal
    )



def skill_capability_tokens(entry: dict[str, Any]) -> set[str]:
    caps: set[str] = set()
    name = str(entry.get("name", ""))
    desc = str(entry.get("description", ""))
    tier = str(entry.get("tier", "")).strip().lower()
    channel = str(entry.get("channel", "")).strip().lower()
    skill_type = str(entry.get("type", "")).strip().lower()

    caps.update(tokenize_text(name))
    caps.update(tokenize_text(desc))

    if tier:
        caps.add(tier)
        caps.add(f"tier:{tier}")
    if channel:
        caps.add(channel)
        caps.add(f"channel:{channel}")
    if skill_type:
        caps.add(skill_type)
        caps.add(f"type:{skill_type}")

    for dep in entry.get("dependencies") or []:
        dep_token = str(dep).strip().lower()
        if dep_token:
            caps.add(dep_token)
            caps.add(f"dep:{dep_token}")
    return caps



def resolve_skills_by_tokens(
    preferred_tokens: Iterable[str],
    *,
    max_skills: int = 8,
    exclude_internal: bool = True,
) -> tuple[str, ...]:
    index = runtime_skill_index()
    if not index:
        return ()

    preferred = {
        str(token).strip().lower()
        for token in preferred_tokens
        if str(token).strip()
    }
    if not preferred:
        return ()

    internal = internal_skill_names() if exclude_internal else set()
    scored: list[tuple[int, str]] = []
    for skill_name, entry in index.items():
        if skill_name in internal:
            continue
        caps = skill_capability_tokens(entry)
        score = sum(1 for token in preferred if token in caps)
        if score > 0:
            scored.append((score, skill_name))

    if not scored:
        return ()

    scored.sort(key=lambda item: (-item[0], item[1]))
    ordered = tuple(name for _, name in scored)
    return ordered[: max(max_skills, 1)]



def resolve_skills_for_text(
    text: str,
    *,
    max_skills: int = 8,
    extra_tokens: Iterable[str] | None = None,
) -> tuple[str, ...]:
    tokens = set(tokenize_text(text or ""))
    if extra_tokens:
        tokens.update(
            str(token).strip().lower()
            for token in extra_tokens
            if str(token).strip()
        )
    selected = resolve_skills_by_tokens(tokens, max_skills=max_skills)
    return filter_runtime_skills(selected)



def list_runtime_skills(*, exclude_internal: bool = True) -> tuple[str, ...]:
    skills = tuple(sorted(runtime_skill_index().keys()))
    return filter_runtime_skills(skills, exclude_internal=exclude_internal)
