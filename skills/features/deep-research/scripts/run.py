#!/usr/bin/env python3
"""
Deep Research - Orchestrator.

Pipeline:
  1. Plan:       LLM decomposes question → sub-questions + search queries
  2. Research:   Parallel sub-questions; each does search + fork/join URL fetch
  3. Synthesize: LLM combines all notes → structured report + summary + sources

Does NOT auto-save. Returns report, summary, and sources list so the main
agent can ask the user whether to save.
"""
import asyncio
import json
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
_lib_dir = Path(__file__).resolve().parent / "_lib"
for _p in (_project_root, _lib_dir):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

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
    return {
        "workspace_root": workspace_root,
        "session_id": session_id,
        "user_id": user_id,
        "db_path": db_path,
    }


def _build_references_section(sources: list[dict]) -> str:
    """Build a ## References section listing all collected URLs."""
    if not sources:
        return ""
    lines = ["\n\n## References\n"]
    for i, src in enumerate(sources, 1):
        title = src.get("title") or src.get("url", "")
        url = src.get("url", "")
        lines.append(f"{i}. [{title}]({url})")
    return "\n".join(lines)


def _build_full_output(summary: str, report: str, sources: list[dict]) -> str:
    """
    Compose final markdown:
      ## Summary
      <summary text>

      <report body>

      ## References
      1. [title](url)
      ...
    """
    parts: list[str] = []
    if summary:
        parts.append(f"## Summary\n\n{summary}")
    if report:
        parts.append(report)
    refs = _build_references_section(sources)
    if refs:
        parts.append(refs)
    return "\n\n".join(parts)


async def _run_deep_research_async(params: dict) -> dict:
    args = params.get("arguments") or params
    question = str(args.get("question", "")).strip()
    if not question:
        return {"error": "question is required", "report": "", "summary": "", "sources": []}

    resolved = _resolve_params(params)
    workspace_root = resolved["workspace_root"]
    session_id = resolved["session_id"]
    user_id = resolved["user_id"]
    db_path = resolved["db_path"]

    provider = get_provider()

    async def execute_tool(skill_name: str, action: str, arguments: dict) -> dict:
        return await execute_skill(
            skill_name=skill_name,
            action=action,
            arguments=arguments,
            workspace_root=workspace_root,
            session_id=session_id,
            user_id=user_id,
            db_path=db_path if db_path.exists() else None,
        )

    # Phase 1: Plan
    plan = await plan_research(question, provider)

    # Phase 2: Research (parallel sub-questions, fork/join fetch inside each)
    notes = await research_parallel(plan.sub_questions, execute_tool)

    # Phase 3: Synthesize
    result = await synthesize(question, notes, provider)

    full_output = _build_full_output(result.summary, result.report, result.sources)

    return {
        "report": full_output,
        "summary": result.summary,
        "sources": result.sources,
        "sources_count": result.sources_count,
    }


def main() -> None:
    params = json.loads(sys.stdin.read())
    result = asyncio.run(_run_deep_research_async(params))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
