"""Shared configuration helpers: repository root, session id length, env parsers.

Constants:
    ROOT: Path to the Sophon repository root (parent of the ``config`` package).
    SESSION_ID_LENGTH: Default hex length for generated session id suffixes (e.g. ``web-`` + hex).
    DEFAULT_API_PORT: Default HTTP listen port when environment variable ``PORT`` is unset (8080).
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SESSION_ID_LENGTH = 8
DEFAULT_API_PORT = 8080

DEFAULT_USER_ID = "default_user"
CAPABILITIES_SKILL_NAME = "capabilities"
DB_FILENAME = "sophon.db"
WORKSPACE_DOCS_DIR = "docs"
WORKSPACE_IMAGES_DIR = "images"
WORKSPACE_PROFILE_DIR = "images/profile"
PROFILE_IMAGE_FILENAME = "me.jpeg"
SOPHON_IMAGE_FILENAME = "sophon.jpeg"


def safe_env_int(key: str, default: str) -> int:
    """Parse an environment variable as int, falling back on invalid values.

    Args:
        key (str): Environment variable name.
        default (str): String form of the default integer if missing or invalid.

    Returns:
        Parsed int, or ``int(default)`` after coercion failure.
    """
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return int(default)


def safe_env_float(key: str, default: str) -> float:
    """Parse an environment variable as float, falling back on invalid values.

    Args:
        key (str): Environment variable name.
        default (str): String form of the default float if missing or invalid.

    Returns:
        Parsed float, or ``float(default)`` after coercion failure.
    """
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return float(default)


# Default upload cap for workspace file ingestion (25 MiB).
WORKSPACE_UPLOAD_MAX_BYTES = safe_env_int("WORKSPACE_UPLOAD_MAX_BYTES", str(25 * 1024 * 1024))
