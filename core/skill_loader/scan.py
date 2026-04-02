"""Scan skills/ tree and build the skill index."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from constants import SKILL_DESCRIPTION_MAX_LEN
from .constants import TIER_MAP, TIER_SUBDIRS, TYPE_DEFAULT_BY_SUBDIR
from .graph import validate_dependency_dag
from .parse import list_scripts, parse_frontmatter, validate_skill_format

logger = logging.getLogger(__name__)


def _skills_base_dir(project_root: Path) -> Path:
    skills_dir = project_root / "skills"
    return skills_dir if skills_dir.exists() else project_root


def build_skill_entry(
    skill_dir: Path,
    skill_md: Path,
    subdir: str,
    *,
    channel: str = "",
) -> dict[str, Any]:
    """Parse a single SKILL.md into an index entry."""
    content = skill_md.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)
    name = fm.get("name", skill_dir.name)
    description = fm.get("description", "")
    validate_skill_format(skill_dir.name, name, description, skill_md)

    meta = fm.get("metadata") or {}
    skill_type = meta.get("type", TYPE_DEFAULT_BY_SUBDIR.get(subdir, "feature"))
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

    tier = TIER_MAP.get(subdir, subdir)

    entry: dict[str, Any] = {
        "name": name,
        "description": description[:SKILL_DESCRIPTION_MAX_LEN],
        "type": skill_type,
        "tier": tier,
        "channel": channel,
        "dependencies": deps,
        "mcp": mcp_servers,
        "dir": str(skill_dir.absolute()),
        "skill_file_path": str(skill_md.absolute()),
        "scripts": list_scripts(skill_dir),
    }
    entry_action = meta.get("entry_action", "")
    if entry_action:
        entry["entry_action"] = str(entry_action).strip()
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


def _scan_skill_roots(project_root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    skills_dir = _skills_base_dir(project_root)

    for subdir in TIER_SUBDIRS:
        subpath = skills_dir / subdir
        if not subpath.exists():
            continue

        if subdir == "optional":
            for channel_dir in subpath.iterdir():
                if not channel_dir.is_dir():
                    continue
                channel = channel_dir.name
                for skill_dir in channel_dir.iterdir():
                    if not skill_dir.is_dir():
                        continue
                    skill_md = skill_dir / "SKILL.md"
                    if not skill_md.exists():
                        continue
                    result[skill_dir.name] = build_skill_entry(
                        skill_dir, skill_md, subdir, channel=channel
                    )
        else:
            for skill_dir in subpath.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue
                result[skill_dir.name] = build_skill_entry(skill_dir, skill_md, subdir)
    return result


def _scan_workflow_agents_root(project_root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    agents_dir = project_root / "workflow" / "agents"
    if not agents_dir.exists():
        return result
    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue
        skill_md = agent_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        result[agent_dir.name] = build_skill_entry(agent_dir, skill_md, "workflow")
    return result


def scan_skills_to_index(project_root: Path) -> dict[str, dict[str, Any]]:
    """Walk primitives/features/tools/optional and workflow/agents."""
    result: dict[str, dict[str, Any]] = {}
    result.update(_scan_skill_roots(project_root))
    result.update(_scan_workflow_agents_root(project_root))

    validate_dependency_dag(result)
    logger.info("skill_loader: scanned %d skills", len(result))
    return result
