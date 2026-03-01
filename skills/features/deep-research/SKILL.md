---
name: deep-research
description: Deep research on a topic. Decomposes question into sub-questions, searches and fetches web sources in parallel, synthesizes a structured report with inline citations and a source list. Use when user asks for in-depth research, comprehensive analysis, or a structured report.
metadata:
  type: feature
  dependencies: "search,filesystem"
---

## Orchestration Guidance

Use when the user asks for in-depth research, comprehensive analysis, or a structured report on a topic.

After `run` returns:
- Present the `summary` to the user immediately.
- Display the full `report` (it includes inline citations and a ## Sources section).
- Ask the user whether they want to save the report to the workspace.
  - If yes: use the `filesystem` skill with tool `write` to save `report` to a file like `research-<topic>.md`.
  - If no: skip saving.

Do NOT auto-save. Always ask first.

## Tools

### run
Run deep research on a question. Returns a structured report, executive summary, key findings, and cited sources.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| question | string | Yes | The research question or topic |

## Output Contract

| Field | Type | Description |
|-------|------|-------------|
| report | string | Full markdown report with sections and inline citations. Includes a `## Sources` section listing all URLs. |
| summary | string | 2-4 sentence executive summary. |
| sources | array | List of `{url, title}` objects — every URL referenced in the report, ordered by relevance. |
| sources_count | int | Total unique sources consulted across all sub-questions. |
| error | string | Present only on failure; describes the error. |
