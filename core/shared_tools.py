"""Compatibility wrapper around the shared `core.tools` package."""

from __future__ import annotations

from core.tools import Tool, ToolCatalog, tool, tool_catalog

__all__ = ["Tool", "ToolCatalog", "tool", "tool_catalog"]
