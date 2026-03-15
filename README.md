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

**Engineering-First Philosophy**
We believe that complex AI capabilities should be designed, tested, and validated by engineers—not generated on-the-fly by AI. Sophon provides the structure for human-curated intelligence while letting AI focus on orchestration.

**Zero-Friction Skill Development**
Drop a `SKILL.md` and script into a folder. Sophon discovers it automatically. No decorators, no registration boilerplate, no framework lock-in. Skills are self-contained, portable, and runtime-agnostic.

**Built for Real-World Complexity**
Sophon handles multi-task workflows through parent-child sessions, supports concurrent task execution, and provides full visibility into what the AI is thinking and doing. Cancel long-running tasks, resume from checkpoints, and maintain full audit trails.

**Safety by Design**
Process isolation ensures skill crashes don't bring down the system. Capability boundaries prevent AI from escaping defined limits. Every skill executes validated scripts—never arbitrary AI-generated code.

**Local-First, Privacy-First**
All data stays on your machine in SQLite. No cloud dependencies, no external vector databases. Your conversations, context, and workflows remain entirely under your control.

---

## Quick Start

```bash
# 1. Clone & setup
git clone https://github.com/William-1995/sophon.git
cd sophon
python -m venv .venv && source .venv/bin/activate

# 2. Configure (choose your provider)
# Configuration files:
#   - .env (main config, created from .env.example)
#   - config.py (system parameters and defaults)
cp .env.example .env
# In .env configure exactly one LLM provider:
#   - DeepSeek (cloud):    DEEPSEEK_API_KEY=...
#   - Qwen/DashScope:      DASHSCOPE_API_KEY=...  (optional QWEN_MODEL, e.g. qwen-plus)
#   - Ollama (local):      ensure Ollama is running, e.g. `ollama run qwen3.5:4b --think=false`
# If multiple are set, Sophon prefers: DeepSeek > Qwen > Ollama.

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
- **@file injection**: Reference files in questions with `@filename`; contents auto-injected. Configurable via `FileInjectionConfig` (skill/action).

**Multi-Session Architecture**
Sophon supports complex multi-task workflows through its parent-child session model:
- **Concurrent tasks**: Run multiple independent tasks simultaneously, each in its own session
- **Parent-child hierarchy**: Background tasks spawn child sessions; parent receives summaries while child contains full details
- **Cancel & resume**: Interrupt long-running tasks anytime. **Resumable** only when checkpoint was saved (streaming cancel); HITL cancel does not offer resume. Resume button shown only when `resumable=true`.
- **Continue anywhere**: Jump into any child session to continue the conversation
- **Session-level concurrency**: Each session operates independently with isolated context and state

**Sub-agent Capabilities**
Built-in feature skills that act as sub-agents:
- **`deep-research`**: Multi-phase research with parallel fetching, LLM denoising, and synthesized reports with citations
- **`troubleshoot`**: Correlates logs, traces, and metrics; generates diagnostic charts
- **`excel-ops`**: Complex Excel manipulations with AI assistance

**Skill Composition**
Engineers can build sophisticated capabilities by composing existing skills:
- **Dependencies**: Declare primitives or features as dependencies in SKILL.md
- **Nested orchestration**: Feature skills call other feature skills as sub-agents
- **DAG validation**: Circular dependencies detected and rejected at load time
- **Unlimited nesting**: Compose skills to any depth, from simple tools to complex workflows

**Engineering-First Design**
- **Human-curated capabilities**: Complex skills designed, tested, and validated by engineers
- **Structured abstraction**: Clear boundaries between what AI decides vs what skills execute
- **Human-in-the-loop (HITL)**: Two modes — (1) generic `request_human_decision` tool: the main agent invokes it when it needs user input; (2) skill-triggered two-phase flow: skills return `__decision_request` (e.g. delete confirmation). Frontend shows modal; user choice flows via `_decision_choice`. Skills can signal early exit with `_abort_run`.
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

**Local Speech-to-Text**
Built-in voice input using faster-whisper (local, no cloud):
- **Models**: tiny, base (default), small, medium, large
- **First-time setup**: Model downloads automatically on first use (~150MB for base model)
- **Languages**: Supports zh, en, auto-detect
- **Configurable**: Set `SOPHON_SPEECH_MODEL` environment variable

**Privacy-First**
- **Your data stays local**: All logs, traces, session context, metrics in SQLite
- **No cloud dependencies**: DuckDuckGo search (no API key needed)
- **LLM-only calls**: Only your configured provider sees prompts

---

## Built-in Skills

**Primitives**
| Skill | Description |
|-------|-------------|
| `search` | Web search via DuckDuckGo |
| `crawler` | Scrape & extract content with Playwright |
| `filesystem` | Read, write, list workspace files. Delete supports two-phase confirmation (HITL). |
| `time` | Timezone conversion, date formatting |
| `deep-recall` | Context exploration powered by RLM-inspired recursive search — intelligently navigates short-term (cached) and long-term (persistent) context across sessions |
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

## Provider Configuration (LLM backends)
Sophon can use different LLM providers; configure **exactly one** in `.env`:

- **DeepSeek (cloud)**: set `DEEPSEEK_API_KEY` (and optional `DEEPSEEK_MODEL`).
- **Qwen/DashScope (cloud)**: set `DASHSCOPE_API_KEY` (and optional `QWEN_MODEL`, e.g. `qwen-plus`).
- **Ollama (local)**: ensure Ollama is running. Default model: `qwen3.5:4b`. Example: `ollama run qwen3.5:4b --think=false`

If you accidentally configure multiple providers, Sophon will prioritize: DeepSeek > Qwen > Ollama.

---

## Coming Soon

- **Agent marketplace** - Share and discover community skills
- **Enhanced file processing** - Advanced Excel, PDF, and document handling capabilities
- **Desktop application** - Native desktop app for seamless OS-level integration

---

## Current Status

Sophon is in early development. Many features are working, but there's still much to improve—performance optimizations, edge case handling, documentation gaps, and broader skill coverage. We believe in building in the open and learning from the community.

If you encounter issues or have ideas, please open an issue or join the discussion. Your feedback helps shape what Sophon becomes.

## Contributing

We welcome contributions of all kinds! Skills are a great starting point—they require no knowledge of core internals.

**Areas where help is especially appreciated:**
- **New skills**: `weather`, `calculator`, `github`, `database`, `calendar`, `email`
- **LLM providers**: OpenAI, Claude, Gemini, local model support
- **File formats**: PDF, Word, image processing capabilities
- **Testing & bug reports**: Real-world usage feedback
- **Documentation**: Tutorials, examples, translations

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT © 2025 William-1995
