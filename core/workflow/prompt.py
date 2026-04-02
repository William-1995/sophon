"""Prompt fragments for workflow orchestration."""

from __future__ import annotations

from core.prompting import (
    CAPABILITY_BLOCKING_PROMPT,
    CURRENT_TIME_CONTEXT_PROMPT,
    THINKING_SEQUENCING_PROMPT,
    WORKSPACE_FILE_DISCOVERY_PROMPT,
)
from core.tools import ToolCatalog, tool_catalog


def _format_tool_list(catalog: ToolCatalog) -> str:
    lines = []
    for tool in catalog.list_tools():
        lines.append(f"- {tool.name}: {tool.description}")
    return "\n".join(lines)


def build_workflow_orchestration_prompt(catalog: ToolCatalog = tool_catalog, current_time: str | None = None) -> str:
    tool_list = _format_tool_list(catalog)
    time_block = f"Current time: {current_time}\n\n" if current_time else ""
    return (
        "You are the workflow orchestrator for a multi-agent collaboration.\n\n"
        f"{time_block}"
        f"{CURRENT_TIME_CONTEXT_PROMPT}\n\n"
        f"{THINKING_SEQUENCING_PROMPT}\n\n"
        f"{WORKSPACE_FILE_DISCOVERY_PROMPT}\n\n"
        f"{CAPABILITY_BLOCKING_PROMPT}\n\n"
        "Available tools:\n"
        f"{tool_list}\n\n"
        "Core rules:\n"
        "- Start in a visible thinking phase instead of jumping directly into planning.\n"
        "- Use thinking to understand intent, discover missing files, and prepare prerequisites before planning.\n"
        "- Produce a structured readiness report at the end of thinking with the next action set to investigate_more, clarify, or plan.\n"
        "- Do not execute a plan immediately after creating it; investigate first and execute only after readiness is confirmed.\n"
        "- If key inputs are missing, move into clarification first and wait for the user reply before planning.\n"
        "- Generate the plan only once for each task unless the user explicitly asks for a re-plan.\n"
        "- After planning, switch directly into execution. Do not re-enter planning during execution.\n"
        "- If a plan already exists in the current workflow state, reuse it instead of creating a new one.\n"
        "- Keep collaboration messages and execution messages separate.\n"
        "- Use collaboration messages for thought, question, answer, decision, and final.\n"
        "- Use execution messages for tool_request, tool_start, tool_result, and tool_error.\n"
        "- Let the orchestrator decide round progression and tool-chain order.\n"
        "- Keep process state visible immediately; final synthesis may be delayed."
    )


WORKFLOW_ORCHESTRATION_PROMPT = build_workflow_orchestration_prompt()
