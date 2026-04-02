"""Crawler tool - wrap the executor's crawler capability."""

from typing import Any, Dict

from core.execution.bridge import execute_skill as core_execute
from . import tool


@tool("crawl", "Crawl and extract content from a webpage")
async def crawl_tool(
    url: str,
    wait_for: int = 2000,
    session_id: str = "",
    workspace_root: str = "",
) -> Dict[str, Any]:
    """Crawl a webpage and return its scraped content."""
    result = await core_execute(
        skill_name="crawler",
        action="scrape",
        arguments={"url": url, "wait_for": wait_for},
        workspace_root=workspace_root,
        session_id=session_id,
    )

    if result.get("error"):
        return {
            "success": False,
            "error": result["error"],
            "content": "",
            "url": url,
        }

    return {
        "success": True,
        "content": result.get("result", ""),
        "url": url,
    }
