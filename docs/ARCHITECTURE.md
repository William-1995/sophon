# Sophon Architecture

This document describes the technical architecture of Sophon.

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
| `skills/primitives/` | Single-purpose tools |
| `skills/features/` | Multi-step orchestrators (sub-agents) |
| `frontend/` | React + TypeScript UI |
| `speech/` | Local speech-to-text |
| `mcp_integration/` | Model Context Protocol support |

## Skill System

### Two-Tier Architecture

**Primitives** (`skills/primitives/`)
- Single-purpose, focused tools
- Examples: search, crawler, filesystem, time, log-analyze, trace, metrics
- Run as isolated subprocesses

**Features** (`skills/features/`)
- Complex capabilities with their own ReAct loops
- Examples: deep-research, troubleshoot, excel-ops
- Act as sub-agents, calling primitives as tools

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

Feature skills can call other feature skills:
```
Main Agent
└── Feature Skill A (depends on Feature Skill B)
    └── Feature Skill B (depends on Primitives)
        ├── Primitive: search
        └── Primitive: crawler
```

**DAG Validation**

Sophon validates the skill dependency graph at load time:
- Detects circular dependencies (A → B → A)
- Rejects cycles before runtime
- Reports dependency errors with clear messages

**Composition Examples**

| Use Case | Composition |
|----------|-------------|
| **Research + Analysis** | `deep-research` → `troubleshoot` for analyzing research findings |
| **Multi-source aggregation** | `search` + `crawler` + `filesystem` for comprehensive data collection |
| **Workflow automation** | Chain `excel-ops` → `filesystem` → `email` for report generation |

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

## Agent Loop (ReAct Pattern)

Located in `core/react/`:

- `main.py` - Main orchestration loop
- `preparation.py` - Run setup, skill selection
- `execution.py` - Tool call execution
- `finalization.py` - Answer generation

### Flow

1. **Round 1**: LLM selects relevant skills from exposed list
2. **Round N**: Thought → Action → Observation (parallel tool execution)
3. **Final**: Summarize with merged, deduplicated references

### Safeguards

| Risk | Mitigation |
|------|------------|
| Concurrency explosion | `max_parallel_tool_calls` (default 10) limits concurrent executions |
| Skill call cycles | Call-stack detection rejects A→B→A; DAG validation at load time |
| File write race | Path-based locks serialize filesystem operations |

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

- Streaming chat with SSE
- Session management
- Async task handling
- OpenAI-compatible endpoints
- AG-UI protocol support

## Configuration

Key environment variables:

- `DEEPSEEK_API_KEY` / `DASHSCOPE_API_KEY` - LLM providers
- `SOPHON_HITL_ENABLED` - Human-in-the-loop toggle
- `SOPHON_THINKING_ENABLED` - LLM reasoning visibility
- `SOPHON_SPEECH_ENABLED` - Local STT toggle
- `SOPHON_MCP_BRIDGE_URL` - MCP integration endpoint

See `config.py` and `constants.py` for all configuration options.

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

The `deep-recall` skill navigates this context spectrum using ideas inspired by [RLM (Recursive Language Model)](https://github.com/ysz/recursive-llm), but adapted for Sophon's context-centric philosophy.

### How Deep-Recall Works

Instead of "remembering" facts, deep-recall **recursively explores the context space**:

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

The system can detect and respond to user emotional cues:
- Sentiment analysis of user inputs
- Adaptive response tone based on detected emotion
- Escalation patterns for frustration or confusion

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
└── Child Session C (excel-ops task)
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

### Human-in-the-Loop

Sophon supports human intervention points:
- **Decision gates**: Agent pauses for human approval before critical actions
- **Progress review**: Real-time visibility into what agent is doing
- **Intervention**: Cancel, modify, or redirect tasks mid-execution
- **Delegation**: Give high-level commands, let agent figure out execution
