"""
MCP Bridge Server - Standalone process for skill subprocesses to call MCP tools.

Run as: python -m mcp_client.bridge_server
Or: python run_mcp_bridge.py

Requires SOPHON_MCP_BRIDGE_URL (e.g. http://127.0.0.1:8765) to be set where
skills run, so they know where to POST tool calls.
"""

import logging
import os
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from uvicorn import run as uvicorn_run

from mcp_client.manager import get_mcp_manager

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8765


def create_app() -> FastAPI:
    """Create ASGI app for MCP bridge."""
    app = FastAPI(title="Sophon MCP Bridge", version="0.1.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "mcp-bridge"}

    @app.post("/internal/mcp/call")
    async def call_tool(req: dict[str, Any] = Body(...)):
        tool = req.get("tool")
        arguments = req.get("arguments") or {}
        if not tool or not isinstance(tool, str):
            raise HTTPException(status_code=400, detail="tool (str) is required")
        mcp = get_mcp_manager()
        result = await mcp.call_tool(tool, arguments)
        return result

    return app


def get_bridge_base_url() -> str | None:
    """Return bridge URL from env. Returns None if not configured (no auto-start)."""
    url = os.environ.get("SOPHON_MCP_BRIDGE_URL")
    return url.rstrip("/") if url else None


def main() -> None:
    """Entry point for standalone bridge process."""
    port = int(os.environ.get("SOPHON_MCP_BRIDGE_PORT", DEFAULT_PORT))
    host = os.environ.get("SOPHON_MCP_BRIDGE_HOST", "127.0.0.1")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.info("MCP bridge starting on %s:%d", host, port)
    app = create_app()
    uvicorn_run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
