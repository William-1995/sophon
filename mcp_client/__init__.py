"""
MCP (Model Context Protocol) Client Integration.

Provides tools from external MCP servers (e.g. DuckDuckGo search) to the ReAct engine.
"""

from mcp_client.adapter import mcp_tool_to_openai_format
from mcp_client.client import MCPServerClient
from mcp_client.manager import MCPManager, get_mcp_manager

__all__ = [
    "MCPServerClient",
    "MCPManager",
    "get_mcp_manager",
    "mcp_tool_to_openai_format",
]
