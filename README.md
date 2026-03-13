# Sophon

> **The skill-native AI agent platform.** Drop a SKILL.md + script into a folder—Sophon discovers, composes, and orchestrates. Zero registration, infinite composability.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**[中文文档](README_CN.md)** | **[Contributing](CONTRIBUTING.md)** | **[Discord](your-discord-link)**

---

## What Makes Sophon Different

Most agent frameworks require you to write glue code to register tools and wire up function calling. Sophon inverts this:

> **The skill definition IS the tool.**

Sophon is not just another agent framework—it's a foundation for an **AI-native OS-level assistant** that handles your work and life. We believe in **engineer-curated capabilities** over AI-generated chaos.

### Engineering-First, Safety-First

Unlike systems that let AI improvise and execute arbitrary code, Sophon operates on a core principle:

**Complex capabilities are designed and validated by engineers, not generated on-the-fly by AI.**

- **Structured abstraction**: Every skill is a carefully designed, tested, and versioned capability
- **Predictable boundaries**: Skills run in isolated subprocesses with defined inputs/outputs
- **Human-curated intelligence**: Engineers define *what* AI can do and *how* it does it
- **No arbitrary execution**: AI orchestrates skills, but cannot create new capabilities or escape defined boundaries

### Skills as Tools. Skills as Sub-agents.

Sophon has a **two-tier skill architecture** that scales from simple tools to complex multi-step workflows:

```
┌─────────────────────────────────────────────────────┐
│  Main Agent (Orchestrator)                          │
│  Analyzes question → Selects skills → Synthesizes   │
└──────────────┬──────────────────────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼────┐          ┌────▼─────┐
│ Primitives      │  │ Features         │
│                 │  │                  │
│ • search        │  │ • deep-research  │
│ • crawler       │  │ • troubleshoot   │
│ • filesystem    │  │ • excel-ops      │
│ • time          │  │                  │
│ • log-analyze   │  │ [Sub-agents with  │
│ • trace         │  │  their own ReAct  │
│ • metrics       │  │  loops]           │
└─────────────────┘  └──────────────────┘
```

- **Primitives**: Single-purpose tools (search, crawl, file I/O). They do one thing well.
- **Features**: Complex capabilities that ARE sub-agents. Each feature runs its own lightweight ReAct loop, calling primitives as tools.

**Example**: `deep-research` is not a tool—it's a sub-agent that plans, dispatches parallel searches, filters results, fetches pages, and synthesizes findings. The main agent just decides *when to invoke it*.

---

## Why Sophon?

| Feature | Sophon | Others |
|---------|--------|--------|
| **Engineer-curated** | Skills designed & tested by humans | AI generates code on-the-fly |
| **Safety boundaries** | Defined capabilities, no arbitrary execution | AI can execute anything |
| **Zero registration** | Drop files, auto-discover | Write glue code, register manually |
| **Process isolation** | Each skill in subprocess (crashes contained) | Shared process (one crash kills all) |
| **Built-in sub-agents** | Feature skills ARE sub-agents | Requires complex implementation |
| **Portable skills** | SKILL.md standard, runtime-agnostic | Framework-specific code |
| **Local-first** | SQLite-only, data stays on your machine | Cloud databases, external vectors |
| **Full observability** | Real-time thinking, tool usage, diagnostics | Black box execution |

---

## Quick Start

```bash
# 1. Clone & setup
git clone https://github.com/William-1995/sophon.git
cd sophon
python -m venv .venv && source .venv/bin/activate

# 2. Configure (add your API key)
cp .env.example .env
# Edit .env: DEEPSEEK_API_KEY=sk-... or DASHSCOPE_API_KEY=...

# 3. Start (installs deps, Playwright, and runs)
python start.py              # API at http://localhost:8080

cd frontend && npm install && npm run dev  # UI at http://localhost:5173
```

---

## Feature Highlights

**Skill-Native Architecture**
- **SKILL.md standard**: Portable across any compatible runtime ([agentskills.io](https://agentskills.io/))
- **Auto-discovery**: Add/remove capabilities by creating/deleting folders
- **Self-contained**: Each skill owns its logic, constants, and dependencies

**Multi-Session Architecture**
Sophon supports complex multi-task workflows through its parent-child session model:
- **Concurrent tasks**: Run multiple independent tasks simultaneously, each in its own session
- **Parent-child hierarchy**: Background tasks spawn child sessions; parent receives summaries while child contains full details
- **Cancel & resume**: Interrupt long-running tasks anytime; resume from any point in session history
- **Continue anywhere**: Jump into any child session to continue the conversation
- **Session-level concurrency**: Each session operates independently with isolated context and state

**Sub-agent Capabilities**
Built-in feature skills that act as sub-agents:
- **`deep-research`**: Multi-phase research with parallel fetching, LLM denoising, and synthesized reports with citations
- **`troubleshoot`**: Correlates logs, traces, and metrics; generates diagnostic charts
- **`excel-ops`**: Complex Excel manipulations with AI assistance

**Engineering-First Design**
- **Human-curated capabilities**: Complex skills designed, tested, and validated by engineers
- **Structured abstraction**: Clear boundaries between what AI decides vs what skills execute
- **Human-in-the-loop**: Delegate tasks to the agent, review progress, intervene when needed
- **Predictable behavior**: No arbitrary code generation or execution

**Security & Safety**
- **Process isolation**: Each skill runs in isolated subprocess; crashes are contained
- **Capability boundaries**: AI orchestrates pre-defined skills, cannot create new capabilities
- **Input validation**: All skill parameters are validated against schemas
- **Resource limits**: Concurrency controls prevent resource exhaustion
- **No arbitrary execution**: Skills execute validated scripts, not AI-generated code
- **Full audit trail**: Every thought, action, and result is logged and inspectable
- **Session tree**: Visualize parent-child session relationships
- **Checkpoint recovery**: Resume interrupted tasks from last checkpoint

**File Processing**
Built-in support for complex document operations including Excel manipulations, with PDF and more formats coming soon.

**Visibility & Observability**
Sophon treats visibility as a first-class citizen:
- **Thinking transparency**: See the LLM's reasoning process in real-time
- **Tool usage tracking**: Watch which skills are called, with what parameters, and their results
- **Built-in diagnostics**: Self-monitoring capabilities for troubleshooting the agent itself
- **Emotion-aware**: Detects and responds to user emotional cues in conversations

**Privacy-First**
- **Your data stays local**: All logs, traces, memory, metrics in SQLite
- **No cloud dependencies**: DuckDuckGo search (no API key needed)
- **LLM-only calls**: Only your configured provider sees prompts

---

## Built-in Skills

**Primitives**
| Skill | Description |
|-------|-------------|
| `search` | Web search via DuckDuckGo |
| `crawler` | Scrape & extract content with Playwright |
| `filesystem` | Read, write, list workspace files |
| `time` | Timezone conversion, date formatting |
| `deep-recall` | Memory search and exploration |
| `log-analyze` | Query and analyze application logs |
| `trace` | Distributed trace analysis |
| `metrics` | Time-series metrics query |
| `diagnostics` | Self-diagnosis and troubleshooting |

**Features (Sub-agents)**
| Skill | Description |
|-------|-------------|
| `deep-research` | Multi-step research with planning, parallel execution, synthesis |
| `troubleshoot` | Root-cause analysis across observability data |
| `excel-ops` | Advanced Excel operations |

---

## Create Your Own Skill

```bash
mkdir -p skills/primitives/my-skill
cat > skills/primitives/my-skill/SKILL.md << 'EOF'
---
name: my-skill
description: "What this skill does and when to use it"
metadata:
  type: primitive
  dependencies: ""
---

## Tools
### run
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| query | string | Yes | Input to process |

## Output Contract
| Field | Type | Description |
|-------|------|-------------|
| result | string | The main output |
| observation | string | LLM-ready text |
| references | array | Optional citations |
EOF

# Create the script
cat > skills/primitives/my-skill/scripts/run.py << 'EOF'
#!/usr/bin/env python3
import json, sys

params = json.load(sys.stdin)
query = params["query"]

# Your logic here
result = f"Processed: {query}"

json.dump({
    "result": result,
    "observation": result
}, sys.stdout)
EOF
chmod +x skills/primitives/my-skill/scripts/run.py
```

Restart Sophon. Your skill is automatically discovered and ready to use.

See [docs/create-skill.md](docs/create-skill.md) for the complete guide.

---

## Documentation

- **[Architecture](docs/ARCHITECTURE.md)** - Technical architecture and design
- **[API Reference](docs/API.md)** - HTTP API endpoints
- **[Creating Skills](docs/create-skill.md)** - Skill authoring guide

---

## Coming Soon

- **Agent marketplace** - Share and discover community skills
- **Enhanced file processing** - Advanced Excel, PDF, and document handling capabilities

---

## Contributing

We welcome contributions! Skills in particular require no knowledge of core internals.

**Good first contributions:**
- New primitive skills: `weather`, `calculator`, `github`, `database`
- New LLM providers: OpenAI, Claude, Gemini
- Improve `deep-research` synthesis quality
- Documentation and examples

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT © 2025 William-1995
