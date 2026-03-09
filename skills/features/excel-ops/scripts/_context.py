"""
Excel-Ops - Context management.

Provides context resolution for excel operations.
"""

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Load skill constants explicitly (avoids conflict with project constants used by core)
_spec = importlib.util.spec_from_file_location(
    "excel_ops_constants",
    Path(__file__).resolve().parent.parent / "constants.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
DB_FILENAME = _mod.DB_FILENAME


@dataclass
class ResolvedContext:
    """Resolved execution context.

    Attributes:
        workspace_root: Root directory of the workspace.
        session_id: Current session identifier.
        user_id: Current user identifier.
        db_path: Path to the database file.
        call_stack: Stack of skill calls for tracking.
    """

    workspace_root: Path
    session_id: str
    user_id: str
    db_path: Path
    call_stack: list[str]


def resolve_context(params: dict[str, Any]) -> ResolvedContext:
    """Resolve execution context from parameters."""
    workspace_root = Path(params.get("workspace_root") or ".").resolve()
    session_id = str(params.get("_executor_session_id") or params.get("session_id") or "default")
    user_id = str(params.get("user_id") or "default_user")
    db_path_raw = params.get("db_path")
    db_path = Path(db_path_raw) if db_path_raw else workspace_root / DB_FILENAME
    call_stack = list(params.get("_call_stack") or [])

    return ResolvedContext(
        workspace_root=workspace_root,
        session_id=session_id,
        user_id=user_id,
        db_path=db_path,
        call_stack=call_stack,
    )


def resolve_path(params: dict[str, Any], path_raw: str) -> Path:
    """Resolve file path relative to workspace.

    Args:
        params: Parameters dict.
        path_raw: Raw path string.

    Returns:
        Resolved absolute Path.
    """
    p = Path(path_raw.strip())
    if p.is_absolute():
        return p

    workspace_root = Path(params.get("workspace_root") or ".").resolve()
    user_id = str(params.get("user_id") or "default_user")

    if p.parts and p.parts[0] == user_id:
        p = Path(*p.parts[1:]) if len(p.parts) > 1 else Path(".")

    return (workspace_root / p).resolve()
