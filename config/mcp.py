"""Optional MCP server definitions and bridge URL placeholder for skill subprocesses."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MCPServerConfig:
    """One stdio-launched MCP server (e.g. Firecrawl when API key is set).

    Attributes:
        name (str): Short id; tool names are prefixed with ``{name}_``.
        command (str): Executable to spawn (``npx``, ``python``, …).
        args (tuple[str, ...]): Arguments after the command.
        load_at_startup (bool): Whether to connect eagerly vs on demand.
        env (tuple[tuple[str, str], ...]): Extra environment pairs for the child process.
    """

    name: str
    command: str
    args: tuple[str, ...]
    load_at_startup: bool = True
    env: tuple[tuple[str, str], ...] = ()

    def tool_prefix(self) -> str:
        """Return the OpenAI-style tool name prefix including trailing underscore.

        Returns:
            String like ``firecrawl_``.
        """
        return f"{self.name}_"


def default_mcp_servers() -> tuple[MCPServerConfig, ...]:
    """Build the default server list from environment (Firecrawl when key present).

    Returns:
        Tuple of ``MCPServerConfig``; empty when no optional keys are set.
    """
    servers: list[MCPServerConfig] = []
    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if firecrawl_key:
        servers.append(
            MCPServerConfig(
                name="firecrawl",
                command="npx",
                args=("-y", "firecrawl-mcp"),
                load_at_startup=True,
                env=(("FIRECRAWL_API_KEY", firecrawl_key),),
            )
        )
    return tuple(servers)


@dataclass(frozen=True)
class MCPConfig:
    """Aggregate MCP settings for the integration layer.

    Attributes:
        servers (tuple[MCPServerConfig, ...]): Active server definitions.
        bridge_base_url (str): Reserved; bridge URL is often resolved at runtime
            from ``SOPHON_MCP_BRIDGE_URL``.
    """

    servers: tuple[MCPServerConfig, ...] = ()
    bridge_base_url: str = ""


def resolve_mcp_config() -> MCPConfig:
    """Factory used by ``AppConfig`` for default MCP wiring.

    Returns:
        ``MCPConfig`` with ``default_mcp_servers()`` and empty ``bridge_base_url``.
    """
    return MCPConfig(servers=default_mcp_servers(), bridge_base_url="")
