# Todos Skill

Plan complex tasks as a todo list with human-in-the-loop confirmation before execution.

## Capabilities

- **plan**: Produces a structured todo list from the user's task description and pauses for user confirmation (Proceed / Cancel).
- For multi-step, long-running, or sensitive tasks where the user wants to review the plan first.

## Dependencies

None. Uses built-in LLM provider.

## Usage

The main agent calls `todos.plan(question="...")` when it detects a complex task. After the user confirms, the agent executes the plan using other skills.
