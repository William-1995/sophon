"""Dependency DAG validation and load-order helpers."""

from __future__ import annotations

from typing import Any


def validate_dependency_dag(index: dict[str, dict[str, Any]]) -> None:
    """Raise if dependency graph contains a cycle. Index: skill_key -> entry with dependencies."""
    visited: set[str] = set()

    def visit(key: str, path: set[str]) -> None:
        if key in path:
            raise ValueError(f"Skill dependency cycle detected involving: {key}")
        if key in visited or key not in index:
            return
        path.add(key)
        try:
            for dep in index[key].get("dependencies") or []:
                dep_key = (dep.strip() if isinstance(dep, str) else str(dep)).strip()
                if not dep_key:
                    continue
                alt = dep_key.replace("_", "-")
                dep_resolved = dep_key if dep_key in index else (alt if alt in index else None)
                if dep_resolved:
                    visit(dep_resolved, path)
        finally:
            path.discard(key)
            visited.add(key)

    for skill_key in index:
        visit(skill_key, set())


def normalize_skill_key(key: str, index: dict[str, Any]) -> str | None:
    """Resolve a skill name/key to the canonical index key."""
    if key in index:
        return key
    alt = key.replace("_", "-")
    if alt in index:
        return alt
    for idx_key, entry in index.items():
        if entry.get("name") in (key, alt):
            return idx_key
    return None


def _resolve_deps_dfs(
    skill_key: str,
    index: dict[str, Any],
    visited: set[str],
    visit_order: list[str],
) -> None:
    if skill_key in visited or skill_key not in index:
        return
    visited.add(skill_key)
    visit_order.append(skill_key)
    for dep_key in index[skill_key].get("dependencies") or []:
        _resolve_deps_dfs(dep_key, index, visited, visit_order)


def compute_load_order(primary_keys: list[str], index: dict[str, Any]) -> list[str]:
    """Return primary skills + transitive deps in DFS order, deduplicated."""
    load_order: list[str] = []
    visited: set[str] = set()
    for primary in primary_keys:
        dfs_result: list[str] = []
        _resolve_deps_dfs(primary, index, visited, dfs_result)
        for skill_key in dfs_result:
            if skill_key not in load_order:
                load_order.append(skill_key)
    return load_order


def briefs_from_load_order(load_order: list[str], index: dict[str, Any]) -> list[dict[str, str]]:
    """Convert load order to [{skill_name, skill_description}]."""
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for skill_key in load_order:
        entry = index.get(skill_key)
        if not entry:
            continue
        name = entry.get("name", skill_key)
        if name in seen:
            continue
        seen.add(name)
        result.append({
            "skill_name": name,
            "skill_description": entry.get("description", ""),
        })
    return result
