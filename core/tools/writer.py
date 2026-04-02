"""Writer tools for generating structured outputs."""

from typing import Any, Dict

from . import tool


@tool("generate_report", "Generate a structured report")
async def generate_report_tool(
    data: Any,
    report_type: str = "general",
    format: str = "markdown",
) -> Dict[str, Any]:
    """Return placeholder report metadata."""
    return {
        "success": True,
        "report": "",
        "format": format,
        "report_type": report_type,
        "data_preview": str(data)[:500] if data else "",
    }


@tool("format_output", "Format content in specific style")
async def format_output_tool(
    content: str,
    target_format: str = "markdown",
) -> Dict[str, Any]:
    """Echo the content with the target format."""
    return {
        "success": True,
        "content": content,
        "format": target_format,
    }
