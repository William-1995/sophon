"""Skill filesystem layout — single source for scan order and tier labels."""

import re

# agentskills.io: name = lowercase letters, numbers, hyphens only; 1-64 chars
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Scan order: primitives -> features -> tools -> optional (align with v7)
TIER_SUBDIRS = ("primitives", "features", "tools", "optional")
TIER_MAP = {"primitives": "primitives", "features": "feature", "tools": "tools", "optional": "optional"}

TYPE_DEFAULT_BY_SUBDIR = {
    "primitives": "primitive",
    "features": "feature",
    "tools": "tools",
    "optional": "feature",
}
