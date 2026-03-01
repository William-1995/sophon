# Sophon

Skill-Native Agent Platform. ReAct + SQLite + Markdown UI.

## Quick Start

```bash
cd sophon
source ../.venv/bin/activate                 # or create a new venv
pip install -r requirements.txt

# API server (port 8080)
python run_api.py

# Frontend dev server (proxy /api → 8080)
cd frontend && npm install && npm run dev    # http://localhost:5173

# CLI
python main.py "Research quantum computing trends"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  Skill selector · @ file mention · Markdown rendering        │
│  Chart (recharts) · Theme · Session sidebar                  │
└───────────────────────────┬─────────────────────────────────┘
                            │ /api  (HTTP + SSE)
┌───────────────────────────▼─────────────────────────────────┐
│                     FastAPI  (port 8080)                     │
│  /chat  /skills  /sessions  /workspace  /health              │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                       ReAct Engine                           │
│                                                              │
│   Thought → Action → Observation  (multi-turn)               │
│                                                              │
│   core/react.py          – main loop                         │
│   core/tool_builder.py   – SKILL.md → OpenAI tool schema     │
│   core/agent_loop.py     – shared loop / parse / evaluate    │
│   core/executor.py       – subprocess runner + timeout map   │
│   core/skill_loader.py   – Anthropic-compatible SKILL.md     │
│   core/providers.py      – DeepSeek / Qwen / OpenAI-compat   │
└──────────┬─────────────────────────────────┬────────────────┘
           │                                 │
┌──────────▼──────────┐         ┌────────────▼───────────────┐
│  Primitives         │         │  Features (composite)       │
│                     │         │                             │
│  filesystem         │         │  troubleshoot               │
│  search             │         │    deps: log-analyze,        │
│  time               │         │          trace, metrics      │
│  memory             │         │                             │
│  log-analyze        │         │  deep-research              │
│  trace              │         │    deps: search, filesystem  │
│  metrics            │         │    phases:                   │
│                     │         │      Plan → Research →       │
└──────────┬──────────┘         │      Synthesize             │
           │                    └────────────┬───────────────┘
           │  execute_skill()                │  scripts/run.py
           │  (subprocess, per-skill timeout)│
           └─────────────────┬──────────────┘
                             │
┌────────────────────────────▼───────────────────────────────┐
│                      SQLite  (sophon.db)                    │
│   logs · traces · metrics · memory · sessions              │
└────────────────────────────────────────────────────────────┘
```

## deep-research Pipeline

```
run.py
  │
  ├─ Phase 1: plan_research(question)
  │    └─ LLM → ResearchPlan
  │         sub_questions: [{question, queries[]}]
  │
  ├─ Phase 2: research_parallel(sub_questions)   ← asyncio.gather
  │    └─ per sub_question:
  │         ├─ serial search queries (execute_tool "search")
  │         └─ fetch_pages(top N URLs)           ← asyncio + Semaphore
  │
  └─ Phase 3: synthesize(question, notes)
       └─ LLM → ResearchResult
            report   : Markdown with inline [Source N] citations
            summary  : 2-4 sentence executive summary
            sources  : [{url, title}] – ALL collected URLs
            sources_count: int

Final output layout:
  ## Summary
  <summary>

  ## Overview / Key Findings / Analysis / Conclusion
  <report body>

  ## References
  1. [title](url)
  ...
```

## Skill Format (Anthropic-compatible SKILL.md)

```yaml
---
name: skill-name          # kebab-case, matches directory name
description: "..."        # ≤ 200 chars
metadata:
  type: primitive | feature
  dependencies: "dep1,dep2"   # features only
license: MIT
compatibility: "sophon>=7"
---

## Orchestration Guidance   # hints for main agent
## Tools                    # tool name / parameter table
## Output Contract          # return field table
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/health | GET | Health check |
| /api/skills | GET | List available skills |
| /api/models | GET | List LLM providers |
| /api/sessions | GET | List sessions |
| /api/sessions/{id}/messages | GET | Session history |
| /api/workspace/files | GET | Workspace file list |
| /api/chat | POST | `{message, skill?, model?}` → SSE stream |

## Skills

| Skill | Type | Description |
|-------|------|-------------|
| filesystem | primitive | Read / write / list workspace files |
| search | primitive | Web search (DuckDuckGo) |
| time | primitive | Time formatting and timezone conversion |
| memory | primitive | Persist and retrieve key-value notes |
| log-analyze | primitive | Query and analyze application logs |
| trace | primitive | Distributed trace analysis |
| metrics | primitive | Time-series metrics query |
| troubleshoot | feature | Orchestrates log-analyze + trace + metrics; renders charts |
| deep-research | feature | Plan → parallel web research → LLM synthesis report |

## Status

- [x] Core: ReAct, tool_builder, agent_loop, executor, skill_loader, providers
- [x] Primitives: filesystem, search, time, memory, log-analyze, trace, metrics
- [x] Features: troubleshoot (charts), deep-research (multi-phase, fork/join fetch)
- [x] API: FastAPI port 8080, SSE streaming, model selection
- [x] Frontend: React + Vite, Markdown rendering, skill select, @ file, sidebar, charts, theme
- [x] Skill format: Anthropic SKILL.md compatible (name validation, license, compatibility)
- [x] Per-skill timeout map (deep-research: 300s)
