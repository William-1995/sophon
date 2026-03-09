"""
Skill Loader - Anthropic-compatible SKILL.md parsing.

Follows agentskills.io / Anthropic Agent Skills format.
"""

import logging
import re
from pathlib import Path
from typing import Any

from constants import (
    SKILL_COMPATIBILITY_MAX_LEN,
    SKILL_DESCRIPTION_MAX_LEN,
    SKILL_NAME_MAX_LEN,
)

logger = logging.getLogger(__name__)

# agentskills.io: name = lowercase letters, numbers, hyphens only; 1-64 chars
_SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _validate_dep_graph_acyclic(index: dict[str, dict[str, Any]]) -> None:
    """Raise if dependency graph contains a cycle. Index: skill_key -> entry with dependencies."""
    visited: set[str] = set()

    def _visit(key: str, path: set[str]) -> None:
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
                    _visit(dep_resolved, path)
        finally:
            path.discard(key)
            visited.add(key)

    for skill_key in index:
        _visit(skill_key, set())


def _get_skills_root() -> Path:
    return Path(__file__).resolve().parent.parent


# ── Frontmatter parsing ───────────────────────────────────────────────────────

def _scalar_field(text: str, key: str) -> str | None:
    """Extract a single-line scalar YAML field value, unquoted."""
    m = re.search(rf"^{key}:\s*(.+)$", text, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip('"').strip("'")


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML frontmatter. Supports Anthropic spec fields + metadata extensions."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}

    text = match.group(1)
    result: dict[str, Any] = {}

    for field in ("name", "description", "license"):
        value = _scalar_field(text, field)
        if value:
            result[field] = value

    compat = _scalar_field(text, "compatibility")
    if compat:
        result["compatibility"] = compat[:SKILL_COMPATIBILITY_MAX_LEN]

    meta_match = re.search(
        r"^metadata:\s*\n((?:  \w+:\s*.+\n?)+)",
        text,
        re.MULTILINE,
    )
    if meta_match:
        meta = {}
        for line in meta_match.group(1).strip().split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"').strip("'")
        result["metadata"] = meta

    return result


# ── Format validation ─────────────────────────────────────────────────────────

def _validate_skill_format(
    skill_dir_name: str,
    name: str,
    description: str,
    skill_path: Path,
) -> None:
    """Log warnings for spec violations. Non-blocking."""
    if not name:
        logger.warning("[skill_loader] %s: missing 'name'", skill_path)
        return
    if len(name) > SKILL_NAME_MAX_LEN:
        logger.warning("[skill_loader] %s: name exceeds %d chars", skill_path, SKILL_NAME_MAX_LEN)
    if not _SKILL_NAME_RE.match(name):
        logger.warning(
            "[skill_loader] %s: name must be lowercase with hyphens (got %r)",
            skill_path, name,
        )
    if name != skill_dir_name:
        logger.warning(
            "[skill_loader] %s: name should match directory (name=%r, dir=%r)",
            skill_path, name, skill_dir_name,
        )
    if not description:
        logger.warning("[skill_loader] %s: missing 'description'", skill_path)
    elif len(description) > SKILL_DESCRIPTION_MAX_LEN:
        logger.warning(
            "[skill_loader] %s: description exceeds %d chars",
            skill_path, SKILL_DESCRIPTION_MAX_LEN,
        )


def _scan_scripts(skill_dir: Path) -> list[str]:
    """List script files (relative to skill dir) sorted by name."""
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return []
    return [str(p.relative_to(skill_dir)) for p in sorted(scripts_dir.glob("*.py"))]


# ── SkillLoader ───────────────────────────────────────────────────────────────

class SkillLoader:
    """Load and cache skills from SKILL.md files."""

    def __init__(self, root: Path | None = None):
        self._root = root or _get_skills_root()
        self._cache: dict[str, dict[str, Any]] = {}

    def load_index(self) -> dict[str, dict[str, Any]]:
        """Load all skills from primitives/ and features/. Result is cached."""
        root_key = str(self._root.resolve())
        if root_key in self._cache:
            return self._cache[root_key]

        result: dict[str, dict[str, Any]] = {}
        skills_dir = self._root / "skills"
        if not skills_dir.exists():
            skills_dir = self._root

        for subdir in ("primitives", "features"):
            subpath = skills_dir / subdir
            if not subpath.exists():
                continue
            for skill_dir in subpath.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue
                entry = self._load_skill_entry(skill_dir, skill_md, subdir)
                result[skill_dir.name] = entry

        _validate_dep_graph_acyclic(result)
        self._cache[root_key] = result
        return result

    def _load_skill_entry(
        self, skill_dir: Path, skill_md: Path, subdir: str
    ) -> dict[str, Any]:
        """Parse a single SKILL.md into an index entry."""
        content = skill_md.read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)
        name = fm.get("name", skill_dir.name)
        description = fm.get("description", "")
        _validate_skill_format(skill_dir.name, name, description, skill_md)

        meta = fm.get("metadata") or {}
        skill_type = meta.get("type", "primitive" if subdir == "primitives" else "feature")
        raw_deps = meta.get("dependencies", "")
        deps: list[str] = (
            [x.strip() for x in raw_deps.split(",") if x.strip()]
            if isinstance(raw_deps, str) and raw_deps
            else (raw_deps if isinstance(raw_deps, list) else [])
        )
        raw_mcp = meta.get("mcp", "")
        mcp_servers: list[str] = (
            [x.strip() for x in raw_mcp.split(",") if x.strip()]
            if isinstance(raw_mcp, str) and raw_mcp
            else (raw_mcp if isinstance(raw_mcp, list) else [])
        )

        entry: dict[str, Any] = {
            "name": name,
            "description": description[:SKILL_DESCRIPTION_MAX_LEN],
            "type": skill_type,
            "dependencies": deps,
            "mcp": mcp_servers,
            "dir": str(skill_dir.absolute()),
            "skill_file_path": str(skill_md.absolute()),
            "scripts": _scan_scripts(skill_dir),
        }
        # Skill declares main-agent entry action (e.g. run); main agent only sees that action
        entry_action = meta.get("entry_action", "")
        if entry_action:
            entry["entry_action"] = str(entry_action).strip()
        # Skill-defined action aliases (e.g. inspect -> structure when script shadows stdlib)
        raw_aliases = meta.get("action_aliases", "")
        if raw_aliases:
            aliases = {}
            for part in str(raw_aliases).split(","):
                part = part.strip()
                if ":" in part:
                    from_a, to_a = part.split(":", 1)
                    aliases[from_a.strip()] = to_a.strip()
            if aliases:
                entry["action_aliases"] = aliases
        for optional in ("license", "compatibility"):
            if fm.get(optional):
                entry[optional] = fm[optional]
        return entry

    def get_skills_brief(self, exposed_skills: set[str] | None = None) -> list[dict[str, str]]:
        """Return brief list of exposed skills for LLM decision-making."""
        index = self.load_index()
        if exposed_skills is None:
            try:
                from config import get_config
                exposed_skills = set(get_config().skills.exposed_skills)
            except Exception:
                exposed_skills = {"filesystem", "troubleshoot", "memory", "time"}
        return [
            {"skill_name": d["name"], "skill_description": d["description"]}
            for d in index.values()
            if d.get("name") in exposed_skills
        ]

    def _normalize_skill_key(self, key: str, index: dict[str, Any]) -> str | None:
        """Resolve a skill name/key to the canonical index key.

        Tries: exact match → hyphen variant → frontmatter name match.
        """
        if key in index:
            return key
        alt = key.replace("_", "-")
        if alt in index:
            return alt
        for idx_key, entry in index.items():
            if entry.get("name") in (key, alt):
                return idx_key
        return None

    def _resolve_deps_transitive(
        self,
        skill_key: str,
        index: dict[str, Any],
        visited: set[str],
        visit_order: list[str],
    ) -> None:
        """DFS: append skill and its dependencies to visit_order. Cycle-safe."""
        if skill_key in visited or skill_key not in index:
            return
        visited.add(skill_key)
        visit_order.append(skill_key)
        for dep_key in index[skill_key].get("dependencies") or []:
            self._resolve_deps_transitive(dep_key, index, visited, visit_order)

    def _compute_load_order(
        self,
        primary_skills: list[str],
        index: dict[str, Any],
    ) -> list[str]:
        """Return primary skills + transitive deps in DFS order, deduplicated."""
        load_order: list[str] = []
        visited: set[str] = set()
        for primary in primary_skills:
            dfs_result: list[str] = []
            self._resolve_deps_transitive(primary, index, visited, dfs_result)
            for skill_key in dfs_result:
                if skill_key not in load_order:
                    load_order.append(skill_key)
        return load_order

    def _brief_from_load_order(
        self,
        load_order: list[str],
        index: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Convert load order to [{skill_name, skill_description}] brief format."""
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

    def get_skills_for_session(
        self,
        skill_filter: str | None = None,
        selected_skills: list[str] | None = None,
    ) -> list[dict[str, str]]:
        """Return skills for tool building (primary + transitive deps).

        skill_filter: explicit UI selection (single skill).
        selected_skills: auto-selected from round-1 LLM inference.
        """
        index = self.load_index()
        raw_primaries = [skill_filter] if skill_filter else (selected_skills or [])
        primaries = [
            k for p in raw_primaries
            if (k := self._normalize_skill_key(p, index)) is not None
        ]
        if not primaries:
            return []

        load_order = self._compute_load_order(primaries, index)
        logger.debug("load_order=%s", load_order)
        return self._brief_from_load_order(load_order, index)

    def get_skill(self, skill_name: str) -> dict[str, Any] | None:
        """Return full skill data including SKILL.md body. None if not found."""
        index = self.load_index()
        key = self._normalize_skill_key(skill_name, index)
        if key is None:
            return None
        data = dict(index[key])
        skill_md = Path(data["skill_file_path"])
        if skill_md.exists():
            data["body"] = skill_md.read_text(encoding="utf-8")
        return data

    def get_skill_scripts(self, skill_name: str) -> list[Path]:
        """Return script file paths for a skill."""
        data = self.get_skill(skill_name)
        if not data:
            return []
        skill_dir = Path(data["dir"])
        return [skill_dir / s for s in data.get("scripts", [])]


# ── Singleton ─────────────────────────────────────────────────────────────────

_shared_loader: SkillLoader | None = None


def get_skill_loader(root: Path | None = None) -> SkillLoader:
    """Return the shared SkillLoader, created on first call."""
    global _shared_loader
    if _shared_loader is None:
        _shared_loader = SkillLoader(root)
    return _shared_loader


# ── Module-level convenience wrappers ─────────────────────────────────────────

def get_skills_brief(root: Path | None = None) -> list[dict[str, str]]:
    return get_skill_loader(root).get_skills_brief()


def get_skills_for_session(
    skill_filter: str | None = None,
    selected_skills: list[str] | None = None,
    root: Path | None = None,
) -> list[dict[str, str]]:
    return get_skill_loader(root).get_skills_for_session(skill_filter, selected_skills)


def activate_skill(skill_name: str, root: Path | None = None) -> dict[str, Any] | None:
    """Alias for get_skill_loader().get_skill(). Kept for backward compatibility."""
    return get_skill_loader(root).get_skill(skill_name)
