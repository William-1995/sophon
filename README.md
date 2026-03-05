# Sophon

> A skill-native AI agent platform. Define skills in Markdown, run them as isolated scripts, and let the LLM orchestrate everything.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**Open source · Self-hosted · Zero vendor lock-in**

---

## Why Sophon?

Most agent frameworks require you to write Python glue code to register tools, wire up function calling, and manage state. Sophon inverts this: **the skill definition is the tool**. Drop a `SKILL.md` and a Python script into a folder — the agent discovers and uses it automatically.

- **Zero registration** — add a directory, the agent picks it up on next start
- **SKILL.md standard** — [Anthropic agentskills.io](https://agentskills.io/)-compatible, portable across agent runtimes
- **Process isolation** — each skill runs in its own subprocess; crashes do not affect the agent
- **SQLite-only persistence** — logs, traces, memory, metrics in one file; your data stays local
- **Streaming UI** — React frontend with Markdown, collapsible references, charts, skill picker

---

## Demo

```
User:  Research the current state of AI coding assistants

Agent: Planning research into 4 sub-questions...
       LLM denoising URLs, selecting top sources...
       Fetching 12 URLs in parallel, synthesizing report...

## Summary
AI coding assistants have matured significantly in 2024-2025...

## Key Findings
1. Context window size is now the primary competitive dimension...
2. Local model quality has closed the gap with cloud APIs...

▾ References (5)   ← collapsible; click to expand
```

Skills return structured `references: [{title, url}]`; the UI merges, dedupes, and renders them in a collapsible section.

---

## Quick Start

Requirements: Python 3.11+, Node 18+ (for frontend)

```bash
git clone https://github.com/William-1995/sophon.git
cd sophon

python -m venv .venv && source .venv/bin/activate   # or `venv\Scripts\activate` on Windows

cp .env.example .env
# Edit .env: add DEEPSEEK_API_KEY or DASHSCOPE_API_KEY

# One-click: installs deps + Playwright browser, then starts API (no "first run" distinction)
python start.py                                  # API -> http://localhost:8080

cd frontend && npm install && npm run dev       # UI  -> http://localhost:5173
```

Or manually: `pip install -r requirements.txt && playwright install chromium && python run_api.py`

---

## Architecture

**Main agent (orchestrator)** — analyzes the question, selects skills, dispatches work, collects results, summarizes. Skills own their output via `observation` and optional `references`; the agent merges references, dedupes by URL, and passes them to the API for rendering.

**Skills (workers)** — each skill reads its spec (SKILL.md), executes, and returns `observation` plus optional `references: [{title, url}]` for the LLM. Skills control their own output format.

**Execution**: Direct (primitive scripts) or sub-agent (feature skills with their own ReAct loop). **Parallel dispatch** — multiple tool calls in one round run in parallel, capped by `max_parallel_tool_calls` to prevent resource exhaustion from LLM hallucination.

### Risk Mitigations

| Risk | Mitigation |
|------|------------|
| **Concurrency explosion** | `max_parallel_tool_calls` (default 10) limits concurrent tool executions per round |
| **Skill call cycles** | Call-stack detection in `execute_skill` rejects A→B→A; DAG validation at load time rejects circular dependencies |
| **File write race** | Path-based locks serialize `filesystem.write` / `delete` / `rename` to the same path |

```
+-------------------------------------------------------------+
|                    React Frontend                            |
|  Skill selector . Markdown rendering . Charts . Sessions     |
+------------------------+------------------------------------+
                         | /api (HTTP + SSE streaming)
+------------------------v------------------------------------+
|                  FastAPI  :8080                              |
+------------------------+------------------------------------+
                         |
+------------------------v------------------------------------+
|              Main Agent (ReAct Orchestrator)                  |
|                                                              |
|  Round 1: select skills (lightweight LLM call)               |
|  Round N: Thought -> Action -> Observation (parallel exec)   |
|  Final:   summarize, reply to user                           |
+----------+---------------------------+-----------------------+
           |                          |
  +--------v----------+    +----------v---------------------+
  |   Primitives      |    |   Features (sub-agents)        |
  |                   |    |                                |
  |  search           |    |  troubleshoot                  |
  |  crawler          |    |    -> log-analyze, trace,      |
  |  filesystem       |    |       metrics, deep-recall     |
  |  time             |    |  deep-research                 |
  |  deep-recall      |    |    -> search, crawler,        |
  |  log-analyze      |    |       filesystem, deep-recall |
  |  trace            |    |                                |
  |  metrics          |    |                                |
  +--------+----------+    +----------+---------------------+
           |   subprocess (isolated)  |
           +--------------+-----------+
                          |
              +-----------v------------+
              |   SQLite (sophon.db)   |
              |  logs . traces .       |
              |  metrics . memory      |
              +------------------------+
```

### Sessions & Sub-agents

- **Skill-as-sub-agent**: feature skills (e.g. `deep-research`, `troubleshoot`) are sub-agents themselves: each runs a lightweight ReAct loop internally, calling primitives as their "tools". The main agent only decides *when to call which skill*; it does not control how skills orchestrate internally.
- **Parent-child multi-session structure**: each async task (e.g. a background long-running call) creates a child session; parent-child links are stored in `session_meta`. The frontend shows sessions as a tree. You can continue from any child session or return to the parent.
- **Parallel multi-session**: the main UI supports switching between sessions; async tasks run independently in child sessions. The parent session receives only a summary (e.g. "background troubleshoot done, click to open detailed child session").

### deep-research Pipeline

```
Plan -> Research (parallel) -> Synthesize
        +-- sub-question 1       LLM merges all notes into
        |   +-- search           structured report with
        |   +-- LLM denoise      inline citations and
        |       (filter noise)    structured references
        |   +-- LLM select URLs
        |   +-- crawler fetch
        +-- sub-question 2...    (asyncio fork/join)
```

LLM denoising filters irrelevant URLs by understanding the research question — no hardcoded patterns. Works for any language and any search result shape.

---

## Skills

### Built-in Primitives

| Skill | Description |
|-------|-------------|
| `search` | Web search via DuckDuckGo — no API key needed |
| `crawler` | Scrape a URL with Playwright + trafilatura extraction |
| `filesystem` | Read, write, list, and manage workspace files |
| `time` | Timezone conversion and date formatting |
| `deep-recall` | Memory exploration — search, analyze by time, explore sessions |
| `log-analyze` | Query and analyze application logs |
| `trace` | Distributed trace analysis |
| `metrics` | Time-series metrics query and write |

### Built-in Features

| Skill | Description |
|-------|-------------|
| `troubleshoot` | Correlates logs, traces, and metrics; renders charts |
| `deep-research` | Multi-phase web research: LLM denoise → select URLs → parallel fetch → synthesis |

### Add Your Own

```
skills/primitives/my-skill/
+-- SKILL.md        <- define name, description, parameters, output contract
+-- scripts/
    +-- run.py      <- reads JSON from stdin, writes JSON to stdout
```

See [docs/create-skill.md](docs/create-skill.md) for the full guide.

---

## SKILL.md Format

Skills follow the [Anthropic Agent Skills](https://agentskills.io/) spec — portable across any compatible runtime.

```markdown
---
name: my-skill
description: "What this skill does and when to use it. 200 chars max."
metadata:
  type: primitive        # or: feature
  dependencies: ""       # features: comma-separated primitive names
license: MIT
compatibility: "sophon>=1"
---

## Orchestration Guidance
When and how the main agent should use this skill.

## Tools

### action-name
Description of this action.

| Parameter | Type   | Required | Description |
|-----------|--------|----------|-------------|
| query     | string | Yes      | Input text  |

## Output Contract

| Field  | Type   | Description             |
|--------|--------|-------------------------|
| result      | string | The main output                     |
| observation | string | LLM-ready text; when present, used verbatim |
| references  | array  | Optional `[{title, url}]` for citations   |
| error       | string | Present only on failure             |
```

---

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/skills` | GET | List available skills |
| `/api/models` | GET | List LLM providers |
| `/api/sessions` | GET | List chat sessions |
| `/api/sessions/{id}/messages` | GET | Session history |
| `/api/workspace/files` | GET | Workspace file list |
| `/api/chat` | POST | `{message, skill?, model?}` -> SSE stream |

---

## Contributing

We welcome contributions of all kinds — new skills in particular require no knowledge of core internals.

See [CONTRIBUTING.md](CONTRIBUTING.md).

Good first contributions:
- Build a new primitive skill: `weather`, `calculator`, `github`, `database`
- Add a new LLM provider: OpenAI, Claude, Gemini
- Improve the `deep-research` synthesis quality
- Write documentation or examples

---

## Security & Privacy

- **Your data stays local** — SQLite stores logs, traces, memory, and metrics in your workspace. No cloud sync unless you add it.
- **LLM calls** — Only your configured provider (DeepSeek, Qwen, etc.) receives prompts. No third-party analytics.
- **Skills** — Run in isolated subprocesses; no arbitrary code execution from the agent itself.

---

## License

MIT (c) 2025 William-1995
