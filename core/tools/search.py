"""Search tool that wraps the executor-based search capability."""

from typing import Any, Dict

from core.execution.bridge import execute_skill as core_execute
from . import tool


@tool("search", "Search the web for information on a given query")
async def search_tool(
    query: str,
    num: int = 10,
    session_id: str = "",
    workspace_root: str = "",
) -> Dict[str, Any]:
    """Execute web search."""
    result = await core_execute(
        skill_name="search",
        action="search",
        arguments={"query": query, "num": num},
        workspace_root=workspace_root,
        session_id=session_id,
    )

    if result.get("error"):
        return {
            "success": False,
            "error": result["error"],
            "sources": [],
        }

    sources = result.get("sources", [])
    if not sources and isinstance(result.get("result"), dict):
        search_data = result["result"]
        results = search_data.get("results", search_data.get("organic", []))
        sources = [
            {"url": item.get("link"), "title": item.get("title", "")}
            for item in results
            if item.get("link")
        ]

    return {
        "success": True,
        "sources": sources,
        "total_found": len(sources),
    }
