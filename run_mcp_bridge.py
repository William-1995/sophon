#!/usr/bin/env python3
"""MCP bridge process for skills that call out to MCP.

Set SOPHON_MCP_BRIDGE_URL (e.g. http://127.0.0.1:8765) before starting the API if required.
Optional: FIRECRAWL_API_KEY for Firecrawl; otherwise follow your MCP server install docs.
"""
import bootstrap_paths

bootstrap_paths.activate()

from mcp_integration.bridge_server import main

if __name__ == "__main__":
    main()
