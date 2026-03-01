"""
MCP Tool to OpenAI function format adapter.

Converts MCP Tool definitions to the OpenAI-compatible function schema
used by the ReAct provider.
"""

from typing import Any

# MCP Tool is a Pydantic model with name, description, inputSchema
# We use typing.Any for the tool param to avoid importing mcp.types at module level
# (allows the module to load even when mcp is not installed for type-checking)


def mcp_tool_to_openai_format(tool: Any, prefix: str) -> dict[str, Any]:
    """Converts an MCP Tool to OpenAI function definition with prefix.

    Args:
        tool: MCP Tool (mcp.types.Tool) with name, description, inputSchema.
        prefix: Tool name prefix (e.g. 'ddg_') to avoid clashes with skills.

    Returns:
        OpenAI-format tool dict: {"type": "function", "function": {...}}.
    """
    name = getattr(tool, "name", "unknown")
    prefixed_name = f"{prefix}{name}"
    description = getattr(tool, "description", "") or ""
    input_schema = getattr(tool, "inputSchema", {}) or {}

    # Ensure we have valid schema structure
    if not isinstance(input_schema, dict):
        input_schema = {"type": "object", "properties": {}}
    if "type" not in input_schema:
        input_schema = {"type": "object", "properties": input_schema}

    return {
        "type": "function",
        "function": {
            "name": prefixed_name,
            "description": description,
            "parameters": input_schema,
        },
    }


def parse_prefixed_tool_name(prefixed_name: str, prefix: str) -> str | None:
    """Extracts the original MCP tool name from a prefixed name.

    Args:
        prefixed_name: Full tool name (e.g. 'ddg_search').
        prefix: Expected prefix (e.g. 'ddg_').

    Returns:
        Original tool name (e.g. 'search') if prefix matches, else None.
    """
    if not prefixed_name.startswith(prefix):
        return None
    return prefixed_name[len(prefix) :] or None
