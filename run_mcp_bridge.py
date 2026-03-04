#!/usr/bin/env python3
"""Run MCP bridge as standalone process.

Skills that use MCP (e.g. crawler) need this process running. Set:
  export SOPHON_MCP_BRIDGE_URL=http://127.0.0.1:8765
before starting the main API.

Default: FreeCrawl (free, no API key). First run: uvx freecrawl-mcp --install-browsers
Optional: Set FIRECRAWL_API_KEY for Firecrawl (paid).
"""
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from mcp_client.bridge_server import main

if __name__ == "__main__":
    main()
