"""Prepend the Sophon repository root to sys.path for entry scripts (start, run_cli, run_api, run_mcp_bridge)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def activate() -> Path:
    """Prepend repository root to sys.path if not already present.

    Returns:
        Path: The repository root directory path.
    """
    s = str(REPO_ROOT)
    if s not in sys.path:
        sys.path.insert(0, s)
    return REPO_ROOT
