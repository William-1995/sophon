"""Shared prompt fragments for reasoning and execution order."""

from __future__ import annotations

THINKING_SEQUENCING_PROMPT = """
Core reasoning order:
- First deeply understand the user's intent, constraints, and missing inputs.
- Use a visible thinking phase before planning so reasoning and preparation can appear in the UI.
- During thinking, you may use lightweight tools to discover files, inspect context, and prepare prerequisites.
- Then choose the tools that can actually satisfy the task.
- Then create a plan from those tools and available information.
- Then execute the plan.
- If required inputs are missing, try to infer them from workspace context first; if still missing, ask the user before selecting a tool that cannot run.
- End the thinking phase with a readiness report whose next action is one of: investigate_more, clarify, or plan.
""".strip()

WORKSPACE_FILE_DISCOVERY_PROMPT = """
File-task discovery:
- For file, PDF, Word, Excel, or CSV tasks, inspect the workspace first when the path is missing.
- Prefer discovering a matching file before asking the user for a path.
- Use the most specific tool available for the discovered file type.
- If discovery fails, ask the user for the missing path or file name.
""".strip()

CAPABILITY_BLOCKING_PROMPT = """
Capability and blocking rules:
- Inspect the currently available tools before claiming that a capability is unavailable.
- If a required tool exists, use that tool instead of saying you cannot perform the task.
- If key inputs are still missing after workspace discovery, ask the user for clarification before creating a plan.
- If a required input is missing, ask for that missing input at most once after workspace discovery fails.
- Do not repeat the same plan proposal, the same proceed question, or the same blocked explanation.
- If the task is blocked by a missing capability or missing input, clearly name the blocker and stop retrying the same plan.
""".strip()

CURRENT_TIME_CONTEXT_PROMPT = """
Current time context:
- Use the current time provided by the orchestrator when reasoning about freshness, deadlines, recency, dates, or time-sensitive output.
- Prefer explicit dates and times over relative words when explaining current state or scheduling.
- If a task depends on time windows, compare against the current time before planning.
""".strip()
