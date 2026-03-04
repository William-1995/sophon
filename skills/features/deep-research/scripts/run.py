#!/usr/bin/env python3
"""
Deep Research - Orchestrator.

Pipeline:
  1. Plan:       LLM decomposes question → sub-questions + search queries
  2. Research:   search → LLM select top URLs → crawler fetch (parallel, configurable concurrency)
  3. Synthesize: LLM combines all notes → structured report + summary + sources

Does NOT auto-save. Returns report, summary, and sources list so the main
agent can ask the user whether to save.
"""
import asyncio
import json
import sys
from pathlib import Path

import os

_project_root = Path(os.environ.get("SOPHON_ROOT", Path(__file__).resolve().parent.parent.parent.parent.parent))
_lib_dir = Path(__file__).resolve().parent / "_lib"
for _p in (_project_root, _lib_dir):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from config import get_config
from constants import DB_FILENAME
from core.executor import execute_skill
from core.providers import get_provider
from planner import plan_research
from researcher import research_parallel
from synthesizer import synthesize


def _resolve_params(params: dict) -> dict:
    workspace_root = Path(params.get("workspace_root", ""))
    session_id = params.get("_executor_session_id", params.get("session_id", "default"))
    user_id = params.get("user_id", "default_user")
    db_path_raw = params.get("db_path")
    db_path = Path(db_path_raw) if db_path_raw else workspace_root / DB_FILENAME
    call_stack = params.get("_call_stack") or []
    return {
        "workspace_root": workspace_root,
        "session_id": session_id,
        "user_id": user_id,
        "db_path": db_path,
        "call_stack": call_stack,
    }


def _build_observation(summary: str, report: str) -> str:
    """Compose observation markdown (Summary + report, no References)."""
    parts: list[str] = []
    if summary:
        parts.append(f"## Summary\n\n{summary}")
    if report:
        parts.append(report)
    return "\n\n".join(parts)


def _sources_to_references(sources: list[dict]) -> list[dict]:
    """Convert sources to unified references format [{title, url}]."""
    return [{"title": s.get("title") or s.get("url", ""), "url": s.get("url", "")} for s in sources if s.get("url")]


async def _run_deep_research_async(params: dict) -> dict:
    args = params.get("arguments") or params
    question = str(args.get("question", "")).strip()
    if not question:
        return {"error": "question is required", "report": "", "summary": "", "sources": [], "observation": "", "answer": ""}

    resolved = _resolve_params(params)
    workspace_root = resolved["workspace_root"]
    session_id = resolved["session_id"]
    user_id = resolved["user_id"]
    db_path = resolved["db_path"]

    provider = get_provider()

    call_stack = resolved.get("call_stack", [])

    async def execute_tool(skill_name: str, action: str, arguments: dict) -> dict:
        return await execute_skill(
            skill_name=skill_name,
            action=action,
            arguments=arguments,
            workspace_root=workspace_root,
            session_id=session_id,
            user_id=user_id,
            db_path=db_path if db_path.exists() else None,
            call_stack=call_stack,
        )

    # Phase 1: Plan
    plan = await plan_research(question, provider)

    # Phase 2: Research (search → LLM select URLs → crawler fetch)
    cfg = get_config().deep_research
    notes = await research_parallel(
        plan.sub_questions,
        execute_tool,
        provider,
        urls_per_sub_question=cfg.urls_per_sub_question,
        crawler_concurrency=cfg.crawler_concurrency,
    )

    # Phase 3: Synthesize
    result = await synthesize(question, notes, provider)

    observation = _build_observation(result.summary, result.report)
    references = _sources_to_references(result.sources)

    return {
        "report": observation,
        "summary": result.summary,
        "sources": result.sources,
        "sources_count": result.sources_count,
        "references": references,
        "observation": observation,
        "answer": observation,
    }


def main() -> None:
    params = json.loads(sys.stdin.read())
    result = asyncio.run(_run_deep_research_async(params))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
