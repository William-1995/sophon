"""
MCP Client - Single-server connection and tool invocation.

Manages lifecycle of one MCP server process (stdio) and provides
list_tools / call_tool operations.
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from config import MCPServerConfig
from mcp_integration.adapter import mcp_tool_to_openai_format, parse_prefixed_tool_name

logger = logging.getLogger(__name__)


def _build_env(config: MCPServerConfig) -> dict[str, str] | None:
    """Build env dict for stdio subprocess from MCPServerConfig.env."""
    if not config.env:
        return None
    base = dict(os.environ)
    for k, v in config.env:
        base[k] = v
    return base


class MCPServerClient:
    """Client for a single MCP server over stdio.

    Uses stdio transport: spawns server process, communicates via stdin/stdout.
    Sessions are created on demand or held for load_at_startup servers.
    """

    def __init__(self, config: MCPServerConfig) -> None:
        """Initializes client with server configuration.

        Args:
            config: MCPServerConfig with command, args, name, load_at_startup.
        """
        self._config = config
        self._prefix = config.tool_prefix()

    @property
    def prefix(self) -> str:
        """Tool name prefix (e.g. 'firecrawl_')."""
        return self._prefix

    @property
    def server_name(self) -> str:
        """Server identifier (e.g. 'firecrawl')."""
        return self._config.name

    @asynccontextmanager
    async def session(self):
        """Async context manager yielding a connected ClientSession.

        Yields:
            ClientSession: Initialized MCP session. Call initialize() before use.
        """
        kwargs: dict[str, Any] = {
            "command": self._config.command,
            "args": list(self._config.args),
        }
        env = _build_env(self._config)
        if env is not None:
            kwargs["env"] = env
        params = StdioServerParameters(**kwargs)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def list_tools(self) -> list[dict[str, Any]]:
        """Lists tools from the server and returns OpenAI-format definitions.

        Returns:
            List of {"type": "function", "function": {...}} dicts with prefixed names.
        """
        tools: list[dict[str, Any]] = []
        async with self.session() as session:
            result = await session.list_tools()
            for t in result.tools:
                tools.append(mcp_tool_to_openai_format(t, self._prefix))
        return tools

    async def call_tool(
        self,
        prefixed_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Invokes a tool by prefixed name.

        Args:
            prefixed_name: Full tool name (e.g. 'ddg_search').
            arguments: Tool arguments dict (e.g. {'query': '...', 'max_results': 10}).

        Returns:
            Result dict with 'content' (str) and optionally 'error' on failure.
        """
        original_name = parse_prefixed_tool_name(prefixed_name, self._prefix)
        if original_name is None:
            return {"error": f"Tool '{prefixed_name}' does not belong to server '{self.server_name}'"}

        args = arguments or {}
        async with self.session() as session:
            try:
                result = await session.call_tool(original_name, arguments=args)
            except Exception as e:
                logger.exception("MCP call_tool failed: %s.%s", self.server_name, original_name)
                return {"error": str(e)}

        return _call_tool_result_to_dict(result)


def _call_tool_result_to_dict(result: Any) -> dict[str, Any]:
    """Converts MCP CallToolResult to a simple dict for ReAct observations."""
    is_error = getattr(result, "isError", False)
    content_blocks = getattr(result, "content", []) or []
    structured = getattr(result, "structuredContent", None)

    parts: list[str] = []
    for block in content_blocks:
        if hasattr(block, "text"):
            parts.append(block.text)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))

    text = "\n".join(parts).strip()
    if structured is not None:
        import json
        text = text or json.dumps(structured, ensure_ascii=False)

    out: dict[str, Any] = {"content": text or "(empty)"}
    if is_error:
        out["error"] = text
    return out
