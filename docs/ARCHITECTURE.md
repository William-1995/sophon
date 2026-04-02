# Sophon Architecture

This document describes the technical architecture of Sophon.

> **Recent changes**: See [CHANGES.md](CHANGES.md) for token optimizations, multi-part handling, and metrics.

## Overview

Sophon uses a modular architecture with clear separation of concerns:

```
React Frontend ←──→ FastAPI ←──→ ReAct Orchestrator ←──→ Skills (subprocess)
                           ↓
                    SQLite (logs, memory, sessions)
```

## Directory Structure

| Directory | Purpose |
|-----------|---------|
| `core/` | ReAct loop orchestration, skill loading, execution |
| `api/` | FastAPI web server, REST endpoints, streaming |
| `db/` | SQLite database layer |
| `providers/` | LLM provider abstractions |
| `skills/primitives/` | Core building blocks (filesystem, memory, time) |
| `skills/tools/` | pdf, word, excel, fetch, search, crawler, log-analyze, trace, metrics |
| `skills/optional/work/` | Work sub-agents (deep-research, troubleshoot) |
| `skills/optional/entertainment/` | Entertainment features (emotion-awareness) |
| `frontend/` | React + TypeScript UI |
| `speech/` | Local speech-to-text |
| `mcp_integration/` | Model Context Protocol support |

## Skill System

### Four-Tier Architecture (v7-aligned)

| Tier | Path | Description |
|------|------|-------------|
| **Primitives** | `skills/primitives/` | Core building blocks: filesystem, memory, time. Run as isolated subprocesses. |
| **Tools** | `skills/tools/` | pdf, word, excel, fetch, search, crawler, log-analyze, trace, metrics. |
| **Optional/Work** | `skills/optional/work/` | Sub-agents with own ReAct loops: deep-research, troubleshoot. |
| **Optional/Entertainment** | `skills/optional/entertainment/` | e.g. emotion-awareness. |

**Scan order**: `primitives` → `features` → `tools` → `optional` (optional uses `optional/<channel>/*`).

### Skill Composition

Sophon enables **unlimited skill composition**—engineers can build sophisticated capabilities by combining existing skills:

**Declaring Dependencies**

In SKILL.md, declare dependencies on other skills:
```yaml
metadata:
  type: feature
  dependencies: "search,crawler,deep-research"
```

This allows your skill to invoke `search`, `crawler`, and even `deep-research` as sub-agents.

**Nested Orchestration**

Optional/Work skills can call other skills:
```
Main Agent
└── workflow (depends on pdf, word, excel, fetch, search, crawler, filesystem)
    ├── excel.read / ingest_file
    ├── search.search / scrape_url
    └── filesystem.save_file
```

**DAG Validation**

Sophon validates the skill dependency graph at load time:
- Detects circular dependencies (A → B → A)
- Rejects cycles before runtime
- Reports dependency errors with clear messages

**Composition Examples**

| Use Case | Composition |
|----------|-------------|
| **Research + Analysis** | `deep-research` → `search`, `crawler`, `filesystem`, `memory` |
| **Document Q&A** | `pdf.structure` → `pdf.parse` with page_range; `word.parse` → `word.to_markdown` |
| **Workflow automation** | `workflow` → `excel`, `search`, `crawler`, `filesystem`; structured saves |

**Benefits**

- **Reusability**: Build once, compose anywhere
- **Modularity**: Complex workflows from simple, tested components
- **Maintainability**: Update primitive, all dependent features benefit
- **Discoverability**: Skills advertise their capabilities via SKILL.md

### Execution Model

1. **Input**: JSON via stdin
2. **Output**: JSON via stdout with optional `references: [{title, url}]`
3. **Optional**: Real-time events via pipe IPC (Unix only)

### SKILL.md Standard

Each skill contains a `SKILL.md` following the Anthropic agentskills.io spec:

```yaml
---
name: skill-name
description: "What this skill does"
metadata:
  type: primitive|feature
  dependencies: "comma,separated,primitives"
---
```

## Main agent vs skills: protocol and events (no hardcoding)

The orchestrator must **not** encode knowledge of specific skill names or tools (e.g. “if `filesystem.delete` then …”). Any skill may be removed; the platform should still run. Coordination uses **contracts** and **events**, not branching on skill identity.

| Mechanism | Role |
|-----------|------|
| **JSON I/O** | stdin/stdout schema, optional fields (`answer`, `references`, `__decision_request`, `_abort_run`, …). Defined in `constants.py` and docs. |
| **Events (IPC)** | Skills emit structured events (`type` + payload). The main loop reacts only to **event type** (see `SophonSkillEventType` in `constants.py`), not to which skill emitted them. |
| **`__decision_request` payload** | Optional protocol keys, e.g. `DECISION_PAYLOAD_AUTO_CONFIRM_IF_PLAN_CONFIRMED`: executor applies generic rules when run state matches (e.g. after `PLAN_CONFIRMED`), without naming skills. |
| **Enums** | Use `SophonSkillEventType` (and similar) instead of magic strings in Python so event types stay centralized and grep-friendly. |

**Example flow (plan → delete, one user confirm):**

1. A planning skill emits `SophonSkillEventType.PLAN_CONFIRMED` after the user approves the plan (via existing HITL on that skill).
2. `run_react` wraps `event_sink` so that event sets `MutableRunState.plan_confirmed`.
3. A delete-related skill returns `__decision_request` whose `payload` includes `auto_confirm_if_plan_confirmed: true` (constant `DECISION_PAYLOAD_AUTO_CONFIRM_IF_PLAN_CONFIRMED`).
4. `execution.py` sees `plan_confirmed` + payload flag and supplies the confirming `_decision_choice` without a second modal—**no checks for skill name or tool name**.

**System prompt** stays abstract: it must not describe individual skills; skill-specific behavior lives in `SKILL.md` and optional protocol fields.

**Path locks** remain adapter-based (`core/adapters/`) so only opt-in skills register path extractors.

**Skill subprocess `PYTHONPATH`:** Built once in `core/runtime_paths.py` and applied in `executor_subprocess.build_run_env(..., script_path=...)`. Order includes `scripts/_lib` (if present), `<skill>/_lib`, the skill’s `scripts/` directory (for sibling imports such as `from parse import …`), the skill directory, repo root, and `skills/primitives`. Skill scripts should not mutate `sys.path` for these; CLI entrypoints use `bootstrap_paths.activate()` at the repo root.

**Task planning (built-in):** `task_plan` is not a filesystem skill. It lives in `core/task_plan/` (prompts, parse, runner). ReAct injects `_tools_brief` from the current OpenAI tool list only for `task_plan.plan` so the planner sees available tools—coupling is localized to `execution.execute_tool_calls_batch` + the built-in tool name constant. Batch-oriented tasks (lists of URLs, rows, files, or records) now carry a batch contract through workflow state and prompts so the orchestrator can keep per-item scope, aggregate progress, and avoid collapsing a collection into a single sample.

**Workflow internals:** `core/cowork/workflow/engine.py` stays focused on orchestration and step execution. Batch detection / progress aggregation / artifact validation live in `analysis.py`, while DB serialization / deserialization lives in `persistence.py`. The frontend consumes `batch_progress` and artifact paths as protocol fields; it does not infer batch semantics or file types on its own.

**Workflow internals:** `core/cowork/workflow/engine.py` stays focused on orchestration and step execution. Batch detection / progress aggregation / artifact validation live in `analysis.py`, while DB serialization / deserialization lives in `persistence.py`. The frontend consumes `batch_progress` and artifact paths as protocol fields; it does not infer batch semantics or file types on its own.

## Agent Loop (ReAct Pattern)

Located in `core/react/`:

| Module | Responsibility |
|--------|----------------|
| `core/react/main.py` | Main orchestration loop; cancel/resume; `abort_run` handling |
| `preparation.py` | Run setup, skill selection, @file injection, tool building |
| `execution.py` | Tool call execution; path locks; delegates HITL replay to `decision_flow.py`; built-in `task_plan`; `check_cancel_after_tools` |
| `decision_flow.py` | Shared `__decision_request` handling: user choice, merge args, second `run_once` |
| `finalization.py` | Answer generation, eval |
| `context.py` | `ImmutableRunContext`, `MutableRunState` (includes `resumable`) |
| `utils.py` | Truncation, checkpoint save, thinking extraction |

### Flow

1. **Round 1**: LLM selects relevant skills from exposed list
2. **Round N**: Thought → Action → Observation (parallel tool execution; path locks per call)
3. **HITL**: If skill returns `__decision_request`, emit DECISION_REQUIRED, re-invoke with `_decision_choice`. If skill returns `_abort_run`, exit immediately.
4. **Final**: Summarize with merged, deduplicated references; return `{cancelled?, resumable?}` when cancelled

### Safeguards

| Risk | Mitigation |
|------|------------|
| Concurrency explosion | `max_parallel_tool_calls` (default 10) limits concurrent executions |
| Skill call cycles | Call-stack detection rejects A→B→A; DAG validation at load time |
| File write race | **Path lock** (see below): registry + adapters serialize `filesystem.write` / `delete` / `rename` to same path |

### Path Lock (Concurrency Control)

To prevent races when parallel tool calls target the same files, Sophon uses a **path lock** system with an adapter-based registry:

- **Registry**: `core/path_lock.py` — `(skill_name, action) → path_extractor(arguments)`. The framework does not know skill internals; adapters opt-in.
- **Adapters**: `core/adapters/filesystem_lock.py` registers extractors for `filesystem.write`, `filesystem.delete`, `filesystem.rename`. Each returns `[path1, path2, ...]` from skill arguments.
- **Execution**: Before running a tool call, `execution.py` calls `get_locks_for_tool_call(workspace_root, skill_name, action, arguments)`, acquires locks for returned paths (in deterministic order to avoid deadlock), then runs the skill.
- **Fallback**: Skills without registered extractors get no locks; no blocking.

### Human-in-the-Loop (HITL)

Sophon supports two HITL modes:

**1. Generic tool: `request_human_decision`**

- **Default off.** When `SOPHON_HITL_ENABLED=true`, the main agent receives a synthetic tool with `message` and `choices`.
- Use only when you explicitly want the model to pause for multi-choice input; routine destructive actions use skill `__decision_request` (e.g. delete).
- Frontend receives `DECISION_REQUIRED` (SSE) and shows a modal; user choice is sent via `POST /api/runs/{run_id}/decision`.

**2. Skill-triggered two-phase flow**

- A skill returns `__decision_request` (constant `DECISION_REQUEST_KEY`) with `{message, choices, payload?}`.
- The execution layer suspends, emits `DECISION_REQUIRED`, and waits for user choice.
- User choice is merged as `_decision_choice` and the skill is re-invoked with the merged arguments.
- If the user cancels (e.g. chooses "Cancel"), the skill returns `_abort_run: true` (constant `ABORT_RUN_KEY`). The main agent stops immediately.
- Optional payload key `DECISION_PAYLOAD_AUTO_CONFIRM_IF_PLAN_CONFIRMED`: when `true` and `state.plan_confirmed` (set by `SophonSkillEventType.PLAN_CONFIRMED`), the executor picks the confirming choice without a second dialog—see *Main agent vs skills* above.

**Constants** (`constants.py`): `DECISION_REQUEST_KEY`, `ABORT_RUN_KEY`, `DECISION_PAYLOAD_AUTO_CONFIRM_IF_PLAN_CONFIRMED`, `SophonSkillEventType`.

**Resumable**: Only when a checkpoint was saved (streaming cancel). HITL cancel does not save a checkpoint; `resumable=false` → frontend does not show Resume button.

### @file Reference

Questions can reference files with `@filename`. The preparation layer (`inject_file_contents` in `preparation.py`) replaces `@filename` with the filename in the question—no content injection. The main agent selects the appropriate skill (pdf, word, filesystem) based on the file reference and passes the path in tool arguments. Each skill receives `workspace_root` + `path` and reads the file itself.

### Workspace Protocol

- **Uploads**: chat and workflow accept multiple local files in one send. The backend stores them under `workspace/{user_id}/docs/` by default, with safe path checks and per-file size limits.
- **Downloads**: the workspace API can package multiple visible workspace files into a zip archive. Hidden/system files (for example `sophon.db` and `.DS_Store`) are filtered out of user-facing listings and downloads.
- **Artifacts**: workflow steps record concrete artifact paths in `output_file` / `output_files` / `artifacts`. The UI treats these as protocol fields and only renders/downloads them; it does not hardcode file types.
- **Batch progress**: the workflow engine exposes a `batch_progress` snapshot for collection-oriented tasks. The frontend renders it as a status panel without deciding batch semantics itself.

### Workspace Protocol

- **Uploads**: chat and workflow accept multiple local files in one send. The backend stores them under `workspace/{user_id}/docs/` by default, with safe path checks and per-file size limits.
- **Downloads**: the workspace API can package multiple visible workspace files into a zip archive. Hidden/system files (for example `sophon.db` and `.DS_Store`) are filtered out of user-facing listings and downloads.
- **Artifacts**: workflow steps record concrete artifact paths in `output_file` / `output_files` / `artifacts`. The UI treats these as protocol fields and only renders/downloads them; it does not hardcode file types.
- **Batch progress**: the workflow engine exposes a `batch_progress` snapshot for collection-oriented tasks. The frontend renders it as a status panel without deciding batch semantics itself.

## Database Layer

SQLite-only persistence:

- Per-user database: `workspace/{user_id}/sophon.db`
- Tables: messages, sessions, memory (FTS5), logs, traces, metrics, checkpoints
- Long-term memory with full-text search
- Session tree structure (parent-child relationships)

## Provider System

Modular LLM provider abstraction in `providers/`:

- `base.py` - Abstract BaseProvider class
- `openai_base.py` - OpenAI-compatible base implementation
- `deepseek.py`, `qwen.py`, `ollama.py` - Concrete providers
- Factory function `get_provider()` with auto-detection

## API Layer

FastAPI server with modular endpoints:

- **Streaming chat** (`/api/chat`): SSE with AG-UI protocol. Emits `RUN_STARTED`, `TOOL_START`, `TOOL_END`, `DECISION_REQUIRED`, `RUN_FINISHED` (with `result.resumable` when cancelled). `decision_handler` pushes DECISION_REQUIRED to stream queue and awaits user choice via `wait_for_decision`.
- **HITL decision** (`POST /api/runs/{run_id}/decision`): Submit user choice; unblocks `wait_for_decision`.
- **Session management**, async tasks, OpenAI-compatible endpoints.

## Configuration

Key environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | — | DeepSeek cloud provider |
| `DASHSCOPE_API_KEY` | — | Qwen/DashScope provider |
| `SOPHON_HITL_ENABLED` | false (default) | When true, add `request_human_decision`; delete confirm stays on filesystem `__decision_request` |
| `SOPHON_THINKING_ENABLED` | true | Parse and emit `<thinking>` blocks |
| `SOPHON_EMOTION_ENABLED` | true | Run emotion segment analysis after each run |
| `SOPHON_SPEECH_ENABLED` | 1 | Local STT (faster-whisper) |
| `SOPHON_MCP_BRIDGE_URL` | — | MCP integration endpoint |

Config classes: `FileInjectionConfig`, `EmotionConfig`, `ReactConfig`, `SkillConfig`, etc. See `config/` package.

### Key Constants (`constants.py`)

| Constant | Value | Purpose |
|----------|-------|---------|
| `DECISION_REQUEST_KEY` | `__decision_request` | Skill output key for two-phase HITL |
| `ABORT_RUN_KEY` | `_abort_run` | Skill output key for early exit |
| `DEFAULT_MODEL` | `qwen3.5:4b` | Default LLM model (Ollama) |
| `FILE_INJECTION_MAX_LEN` | 3000 | Max chars per @file content |

## Event IPC (Subprocess Progress)

Skills can emit structured events to parent via pipe:

- **Transport**: Pipe (Unix only; Windows runs normally without events)
- **Format**: JSON (default) or MessagePack
- **Protocol**: `{"sophon_event": <event>}`

Child side:
```python
from core.ipc import get_reporter
reporter = get_reporter()
if reporter:
    reporter.emit("progress", {"phase": "fetch", "current": 5, "total": 20})
```

Parent side:
```python
from core.ipc import PipeEventChannel
channel = PipeEventChannel(read_fd, format_name="json")
channel.start()
async for event in channel.read_events():
    event_sink(event)
```

## Context Management & RLM-Inspired Architecture

Sophon has a fundamental design principle: **There is no "memory"—only context at different stages of persistence.**

Unlike traditional agent systems that treat "memory" as a separate concept, Sophon views all information as **context** that exists on a spectrum from short-term (cached) to long-term (persistent).

### No Memory, Only Context

- **Short-term context**: Current conversation, recent messages, cached intermediate results
- **Long-term context**: Persisted session histories, skill outputs, references
- **Cross-session context**: Relationships between parent and child sessions

The `memory` skill navigates this context spectrum using ideas inspired by [RLM (Recursive Language Model)](https://github.com/ysz/recursive-llm), but adapted for Sophon's context-centric philosophy.

### How Memory Works

Instead of "remembering" facts, memory **recursively explores the context space**:

1. **Query Analysis**: Understand what context is needed
2. **Recursive Exploration**: Search across short-term and long-term context layers
3. **Context Assembly**: Retrieve relevant context segments, not "memories"
4. **LLM-Augmented**: Use LLM to determine which context segments are relevant

### RLM-Inspired Context Navigation

Borrowing from RLM's recursive approach:
- **Hierarchical exploration**: Search context at multiple time scales (recent, day, week, month)
- **Iterative refinement**: Narrow down from broad context to specific segments
- **Cross-reference**: Link related context across different sessions and times
- **No embedding required**: Uses structured query + LLM reasoning instead of vector similarity

### Why This Matters

Traditional "memory" systems:
- Create artificial boundaries between "working memory" and "long-term memory"
- Often rely on brittle vector similarity
- Lose the narrative structure of conversations

Sophon's context approach:
- **Continuous spectrum**: Context flows naturally from recent to historical
- **Structured retrieval**: Uses session trees, timestamps, and skill outputs
- **Narrative preservation**: Maintains the flow and relationships between ideas
- **Engineer-curated**: Context structure is designed, not emergent

### Use Cases

- **Contextual continuity**: "What did we discuss about the API design in our last session?"
- **Cross-session insights**: Finding related discussions across different projects
- **Temporal navigation**: "Show me how this requirement evolved over the past month"
- **Skill output tracking**: Retrieve previous tool results without re-execution

## Design Principles

1. **Zero Registration**: Skills auto-discovered from directory structure
2. **Process Isolation**: Each skill runs in subprocess; crashes contained
3. **Self-Contained Skills**: Each skill owns constants, can be added/removed independently
4. **SQLite-Only**: All data in single file, zero external dependencies
5. **Streaming-First**: Real-time UI updates via SSE with AG-UI protocol
6. **Anthropic Compatible**: SKILL.md format follows agentskills.io spec

## Visibility & Observability

Sophon treats visibility as a first-class design principle:

### Thinking Transparency

Every step of the LLM's reasoning is captured and streamable:
- **Thought events**: LLM reasoning process exposed via SSE
- **Action logging**: Every tool call with parameters and results
- **Observation tracking**: Skill outputs and references
- **Session replay**: Complete history of agent interactions

### Built-in Diagnostics

Sophon includes self-monitoring capabilities:

| Capability | Description |
|------------|-------------|
| **Self-diagnosis** | Agent can analyze its own logs and traces |
| **Performance metrics** | Query execution times, LLM token usage |
| **Error correlation** | Link errors across skills and sessions |
| **Health checks** | Built-in `/api/health` with detailed status |

### Emotion Awareness

Optional feature (`SOPHON_EMOTION_ENABLED`, default on). An async sub-agent analyzes session segments (user questions + assistant replies) via LLM and persists summaries to `emotion_segments` table.

- **Storage**: `db/emotion.py` — inserts segments with `emotion_label` (e.g. `neutral`, `frustrated`, `satisfied`).
- **Orb ring**: Frontend `EMOTION_RING_COLORS` maps `emotion_label` → hex color. Six distinct colors for: satisfied/relieved/amused (green), neutral (gray), frustrated (orange), disappointed (red), anxious (yellow), confused (amber).
- **API**: `GET /api/emotion/latest` returns `{emotion_label, session_id}` for orb ring. `EMOTION_UPDATED` SSE event pushes updates.
- **Skill**: `emotion-awareness.run` (optional) retrieves segments for "how's my mood" queries. Task helper `enqueue_segment_analysis` runs after each completed run when emotion is enabled.

### Real-Time Streaming

Skills emit structured events via pipe IPC (Unix):
```
progress: { phase: "fetch", current: 5, total: 20 }
thought: "Analyzing search results..."
action: { tool: "crawler", url: "..." }
observation: { result: "...", references: [...] }
```

## Security Model

Sophon follows an **engineering-first, safety-first** security model:

### Capability Boundaries

**Human-Curated Intelligence**: All complex capabilities are designed, tested, and validated by engineers. AI orchestrates skills but cannot:
- Create new capabilities on-the-fly
- Modify existing skill implementations
- Execute arbitrary code outside defined boundaries
- Access resources not explicitly granted to a skill

### Execution Safety

| Mechanism | Implementation |
|-----------|----------------|
| **Process Isolation** | Each skill runs in isolated subprocess |
| **Input Validation** | All parameters validated against SKILL.md schemas |
| **Resource Limits** | `max_parallel_tool_calls` prevents exhaustion |
| **No Arbitrary Execution** | Skills execute validated scripts, not AI-generated code |
| **Capability Boundaries** | AI can only invoke pre-defined skills |

### Trust Boundaries

```
User Query → LLM (orchestration only) → Pre-defined Skills → System Resources
                ↑                           ↓
           Cannot create new          Isolated execution
           capabilities               with defined I/O
```

This design ensures predictable behavior even when interacting with powerful AI models, as the AI's role is strictly limited to orchestrating human-designed capabilities.

## Multi-Session Architecture

Sophon implements a parent-child session tree for managing complex, multi-task workflows:

### Session Hierarchy

```
Main Session
├── Child Session A (deep-research task)
│   └── Grandchild Session A1 (follow-up question)
├── Child Session B (troubleshoot task)
└── Child Session C (workflow task)
```

### Key Capabilities

**Concurrent Task Execution**
- Run multiple independent tasks simultaneously
- Each task operates in its own isolated session
- Sessions share no context unless explicitly linked

**Parent-Child Relationships**
- Background long-running tasks spawn child sessions
- Parent receives summary: "Deep research complete, view details in child session"
- Child contains full conversation history and intermediate results
- Navigate between parent and children via session tree UI

**Cancel & Resume**
- Interrupt long-running tasks at any point via Cancel button
- Resume from last checkpoint
- Session state persists in SQLite for recovery

**Session-Level Concurrency**
- Each session has isolated context, memory, and skill state
- No interference between concurrent sessions
- Resource limits apply per-session to prevent exhaustion

### Async Task Flow

1. User initiates long-running task in main session
2. Task spawns child session with async execution
3. Main session continues independently
4. Child session streams progress events to UI
5. User can:
   - Continue main session
   - Switch to child session to monitor
   - Cancel child session anytime
   - Resume child session later

### Human-in-the-Loop (Summary)

See [Human-in-the-Loop (HITL)](#human-in-the-loop-hitl) above for full design. Key points:

- **Decision gates**: Agent pauses for human approval before critical actions; skills can request confirmation via `__decision_request`
- **Progress review**: Real-time visibility via SSE (TOOL_START, TOOL_END, THINKING, DECISION_REQUIRED)
- **Intervention**: Cancel, modify, or redirect; `_abort_run` signals early exit when user cancels HITL
- **Delegation**: Give high-level commands; agent uses `request_human_decision` when it needs user input
