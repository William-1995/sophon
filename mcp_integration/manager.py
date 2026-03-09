"""
MCP Manager - Aggregates tools from configured MCP servers.

Provides a single interface for ReAct: merged tool definitions and
tool call routing by prefix.
"""

import logging
from typing import Any

from config import MCPConfig, get_config
from mcp_integration.client import MCPServerClient

logger = logging.getLogger(__name__)

# Mutable container avoids global keyword (we mutate in place, never rebind).
_manager: list["MCPManager"] = []


class MCPManager:
    """Manages MCP server clients and aggregates their tools."""

    def __init__(self, config: MCPConfig | None = None) -> None:
        cfg = config or get_config().mcp
        self._clients: dict[str, MCPServerClient] = {
            s.name: MCPServerClient(s) for s in cfg.servers
        }
        self._prefix_to_server: dict[str, str] = {
            c.prefix: c.server_name for c in self._clients.values()
        }

    async def get_tools(
        self, load_at_startup_only: bool = False
    ) -> list[dict[str, Any]]:
        """Returns OpenAI-format tools from configured MCP servers."""
        tools: list[dict[str, Any]] = []
        cfg = get_config().mcp

        for server in cfg.servers:
            if load_at_startup_only and not server.load_at_startup:
                continue
            client = self._clients.get(server.name)
            if not client:
                continue
            try:
                server_tools = await client.list_tools()
                tools.extend(server_tools)
            except Exception as e:
                logger.warning("Failed to list tools from MCP server %s: %s", server.name, e)

        return tools

    def is_mcp_tool(self, tool_name: str) -> bool:
        """Checks if a tool name belongs to an MCP server."""
        for prefix in self._prefix_to_server:
            if tool_name.startswith(prefix):
                return True
        return False

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Dispatches a tool call to the appropriate MCP server."""
        for prefix, server_name in self._prefix_to_server.items():
            if tool_name.startswith(prefix):
                client = self._clients.get(server_name)
                if client:
                    return await client.call_tool(tool_name, arguments)
                break

        return {"error": f"No MCP client for tool '{tool_name}'"}


def get_mcp_manager(config: MCPConfig | None = None) -> MCPManager:
    """Returns the shared MCP manager instance."""
    if not _manager:
        _manager.append(MCPManager(config))
    return _manager[0]
