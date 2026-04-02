"""Skill-local literals for deep-research (self-contained copy of workspace layout).

These mirror project defaults so the skill tree can be moved or vendored without
importing top-level ``constants``. Prefer app-level constants for new global policy.

Constants:
    DB_FILENAME: Default SQLite filename under the workspace.
    CAPABILITIES_SKILL_NAME: Internal skill name for capability listing.
    DEFAULT_USER_ID: Default workspace user id segment.
    WORKSPACE_*: Relative dirs under ``workspace/{user_id}/``.
    PROFILE_IMAGE_FILENAME / SOPHON_IMAGE_FILENAME: Avatar basenames.
"""

# Database
DB_FILENAME = "sophon.db"

# Skill name constants
CAPABILITIES_SKILL_NAME = "capabilities"

# User constants
DEFAULT_USER_ID = "default_user"

# Workspace directories
WORKSPACE_DOCS_DIR = "docs"
WORKSPACE_IMAGES_DIR = "images"
WORKSPACE_PROFILE_DIR = "images/profile"

# Image filenames
PROFILE_IMAGE_FILENAME = "me.jpeg"
SOPHON_IMAGE_FILENAME = "sophon.jpeg"

# Preview limits
DEEP_RESEARCH_ERROR_PREVIEW_MAX_CHARS = 120
DEEP_RESEARCH_SOURCE_TEXT_PREVIEW_MAX_CHARS = 800
