---
name: todos
description: Plan complex tasks as a todo list with human confirmation before execution. Use when the user's request involves multiple steps, long-running work, or requires approval before proceeding.
metadata:
  type: primitive
  entry_action: plan
  dependencies: ""
---

## Orchestration Guidance

**When to use:** For complex, multi-step tasks where the user may want to review and approve the plan before execution. Examples: filling multiple Excel columns from web data, deep research with citations, bulk file operations, multi-phase workflows.

**When NOT to use:** Simple questions, single-step actions, or when the user has already approved (e.g. "just do it"). For quick tasks, call the appropriate skill directly.

**Flow:**
1. Agent calls `todos.plan(question="...")` with the user's request
2. Skill produces a todo list and pauses for human confirmation (HITL)
3. User chooses "Proceed" or "Cancel"
4. If Proceed, agent continues executing the plan using other skills

**Rules:**
- One plan call per complex request. Do not call todos.plan for every message.
- After user confirms, execute the plan step-by-step using the listed skills.

## Tools

### plan
Produce a todo plan for a complex task and request user confirmation before execution.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| question | string | Yes | The user's task or question to plan |

Returns: plan (list of todo items), observation. Triggers HITL: user must confirm before agent proceeds.
