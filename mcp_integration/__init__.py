"""
MCP (Model Context Protocol) Integration.

All MCP-related logic: client, adapter, manager, bridge server.
Tools from external MCP servers (e.g. Firecrawl) are exposed to skills via the bridge.
"""

from mcp_integration.adapter import mcp_tool_to_openai_format
from mcp_integration.client import MCPServerClient
from mcp_integration.manager import MCPManager, get_mcp_manager

__all__ = [
    "MCPServerClient",
    "MCPManager",
    "get_mcp_manager",
    "mcp_tool_to_openai_format",
]
