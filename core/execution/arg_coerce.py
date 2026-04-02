"""
Workbook path resolution for excel skill subprocess stdin.

Matches ``skills/tools/excel/SKILL.md``: only ``file`` (primary) and ``path`` (alias).
Executor merges tool ``arguments`` onto the top-level params dict; optional nested
``arguments`` is still checked for double-wrapped payloads. No other key names,
no deep scan — wrong keys surface as clear skill errors so the LLM can fix the call.
"""

from __future__ import annotations

from typing import Any

# Documented in excel SKILL.md only (ordered: prefer `file`)
_WORKBOOK_PATH_KEYS: tuple[str, ...] = ("file", "path")

# Shown in excel script JSON errors when file/path missing
MISSING_WORKBOOK_PATH_HELP = (
    "Missing workbook path: pass `file` (or `path`) in arguments as a path relative to the workspace."
)


def normalize_workbook_path_string(s: str) -> str:
    """Strip chat-style @workspace refs (e.g. @docs/a.xlsx -> docs/a.xlsx)."""
    t = str(s).strip()
    if not t:
        return ""
    while t.startswith("@"):
        t = t[1:].lstrip("/").strip()
    return t


def workbook_path_from_dict(d: dict | None) -> str:
    """Return workbook path from a flat dict using only SKILL-documented keys."""
    if not isinstance(d, dict):
        return ""
    for key in _WORKBOOK_PATH_KEYS:
        v = d.get(key)
        if v is None:
            continue
        if isinstance(v, list) and v:
            v = v[0]
        s = normalize_workbook_path_string(str(v))
        if s:
            return s
    return ""


def workbook_path_from_tool_stdin(params: dict[str, Any]) -> str:
    """Resolve workbook path from skill stdin (merged params + optional nested arguments)."""
    found = workbook_path_from_dict(params)
    if found:
        return found
    inner = params.get("arguments")
    if isinstance(inner, dict):
        return workbook_path_from_dict(inner)
    return ""
