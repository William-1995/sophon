"""SKILL.md frontmatter parsing and per-skill validation."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from constants import (
    SKILL_COMPATIBILITY_MAX_LEN,
    SKILL_DESCRIPTION_MAX_LEN,
    SKILL_NAME_MAX_LEN,
)

from .constants import SKILL_NAME_PATTERN

logger = logging.getLogger(__name__)


def scalar_field(text: str, key: str) -> str | None:
    """Extract a single-line scalar YAML field value, unquoted."""
    m = re.search(rf"^{key}:\s*(.+)$", text, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip('"').strip("'")


def parse_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML frontmatter. Supports Anthropic spec fields + metadata extensions."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}

    text = match.group(1)
    result: dict[str, Any] = {}

    for field in ("name", "description", "license"):
        value = scalar_field(text, field)
        if value:
            result[field] = value

    compat = scalar_field(text, "compatibility")
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


def validate_skill_format(
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
    if not SKILL_NAME_PATTERN.match(name):
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


def list_scripts(skill_dir: Path) -> list[str]:
    """List script files (relative to skill dir) sorted by name."""
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return []
    return [str(p.relative_to(skill_dir)) for p in sorted(scripts_dir.glob("*.py"))]
