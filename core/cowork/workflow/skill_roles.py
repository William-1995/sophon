"""Workflow role definitions + runtime skill resolution.

Roles are discovered from runtime workflow agents. No hardcoded role defaults and
no implicit fallback role/skill expansion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.skill_loader.capability_resolver import (
    filter_runtime_skills,
    resolve_skills_by_tokens,
    runtime_skill_index,
    tokenize_text,
)


@dataclass(frozen=True)
class WorkflowRoleSpec:
    id: str
    match_tokens: tuple[str, ...]
    max_skills: int = 8
    instruction: str = ""


_ROLE_REGISTRY: dict[str, WorkflowRoleSpec] = {}


def normalize_role_id(raw: str) -> str:
    if not raw or not str(raw).strip():
        raise ValueError("workflow step role is required")
    return str(raw).strip().lower().replace(" ", "_")



def _default_role_instruction(role_id: str) -> str:
    role_text = role_id.replace("_", " ")
    return (
        f"You are the {role_text} stage. "
        "Use only capabilities that are currently available. "
        "Do not assume any specific skill exists; if required capability is missing, "
        "state the blocker explicitly."
    )



def register_role_spec(spec: WorkflowRoleSpec, *, override: bool = False) -> None:
    key = normalize_role_id(spec.id)
    if not override and key in _ROLE_REGISTRY:
        raise ValueError(f"workflow role {spec.id!r} is already registered")
    _ROLE_REGISTRY[key] = WorkflowRoleSpec(
        id=key,
        match_tokens=tuple(
            str(token).strip().lower()
            for token in spec.match_tokens
            if str(token).strip()
        ),
        max_skills=max(int(spec.max_skills), 1),
        instruction=str(spec.instruction).strip() or _default_role_instruction(key),
    )



def register_role_specs(specs: Iterable[WorkflowRoleSpec], *, override: bool = False) -> None:
    for spec in specs:
        register_role_spec(spec, override=override)



def get_role_spec(role_id: str) -> WorkflowRoleSpec:
    rid = normalize_role_id(role_id)
    try:
        return _ROLE_REGISTRY[rid]
    except KeyError as exc:
        raise ValueError(
            f"unknown workflow role {role_id!r}; allowed: {sorted(_ROLE_REGISTRY.keys())}"
        ) from exc



def _workflow_agent_specs() -> tuple[WorkflowRoleSpec, ...]:
    specs: list[WorkflowRoleSpec] = []
    for entry in runtime_skill_index().values():
        if str(entry.get("type", "")).lower() != "agent":
            continue
        if str(entry.get("tier", "")).lower() != "workflow":
            continue
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        role_id = normalize_role_id(name.replace("-", "_"))
        dep_tokens = " ".join(str(dep) for dep in (entry.get("dependencies") or []))
        role_tokens = tuple(
            sorted(tokenize_text(" ".join((role_id, name, str(entry.get("description", "")), dep_tokens))))
        )
        if not role_tokens:
            role_tokens = tuple(sorted(tokenize_text(role_id.replace("_", " "))))
        specs.append(
            WorkflowRoleSpec(
                id=role_id,
                match_tokens=role_tokens,
                max_skills=8,
                instruction=_default_role_instruction(role_id),
            )
        )
    return tuple(specs)



def _bootstrap_registry() -> None:
    _ROLE_REGISTRY.clear()
    register_role_specs(_workflow_agent_specs(), override=True)



def resolve_role_skills(role_id: str, override: list[str] | None) -> tuple[str, tuple[str, ...], str]:
    """Resolve role to skills from runtime scan; no fallback expansion."""
    spec = get_role_spec(role_id)
    if override:
        selected = filter_runtime_skills(override)
        if selected:
            return spec.id, selected, spec.instruction

    selected = resolve_skills_by_tokens(spec.match_tokens, max_skills=spec.max_skills)
    selected = filter_runtime_skills(selected)
    return spec.id, selected, spec.instruction



def list_role_ids() -> list[str]:
    return sorted(_ROLE_REGISTRY.keys())


_bootstrap_registry()
