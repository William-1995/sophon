# Sophon Design Principles

Sophon is both a personal assistant product and a learning template for building agentic systems.  
Version 0.1 proved the system can run. Version 0.2 focuses on making the boundaries, protocols, and responsibilities clear enough that other engineers can read the docs and understand how to contribute.

## What Sophon Is

- A local-first personal assistant.
- A workflow system for multi-step, multi-agent tasks.
- A template for understanding how chat, tools, skills, workflows, and workspace files fit together.
- An open-source web product with room to grow into a broader assistant / digital worker platform.

## What Sophon Is Not

- Not a single prompt doing everything.
- Not a frontend that hardcodes business logic.
- Not a workflow engine that knows every tool’s internals.
- Not a place where every new use case becomes a special case.

## Core Principles

### Protocol first
We prefer shared contracts over ad-hoc wiring.

- Frontend displays protocol state.
- Workflow orchestrates protocol steps.
- Tools and skills implement capabilities behind those contracts.
- The UI should not decide batch semantics, file types, or step behavior.

### Boundary first
Each layer should own one responsibility.

- Chat and workflow share capabilities, but not responsibilities.
- Tools execute actions.
- Skills compose tools.
- Workflow coordinates multi-step execution.
- Persistence stores state.
- Frontend renders state.

### Human-auditable
Users should be able to understand what happened.

- Thinking, investigation, planning, execution, and results should be visible.
- Intermediate artifacts can be preserved.
- Final outputs should point to real workspace files.

### Workspace-bound
User-visible outputs belong to the user workspace.

- Uploads default to `workspace/{user_id}/docs/`.
- Downloads should package visible workspace files only.
- Hidden or system files should not leak into UI or downloads.

### Replaceable
The system should allow skills, tools, and even orchestration pieces to be swapped or removed without collapsing the whole product.

### Ecosystem compatible
Sophon should stay compatible with other agent ecosystems without adopting their internals as core truth.

- Use internal contracts first, adapters second.
- Treat Claude Code skill packages, sub-agents, commands, memory, and MCP as import/export targets.
- Treat OpenAI Codex workflows and MCP as integration targets.
- Keep provider-specific shapes out of core orchestration and out of the frontend.

## How to Read the Repository

- `README.md` / `README_CN.md` — product overview and public-facing positioning.
- `docs/ARCHITECTURE.md` — system boundaries, contracts, and runtime behavior.
- `docs/ECOSYSTEM_COMPATIBILITY.md` — how Sophon maps to Claude Code, Codex, and MCP ecosystems.
- `docs/API.md` — API reference.
- `docs/ROADMAP.md` — what the merged 0.2/0.2.1 release and 0.3 are meant to evolve toward.
- `docs/FRONTEND_DIRECTION.md` — UI layering and interaction guidance inspired by Claude Code, not copied from it.
