#!/usr/bin/env python3
"""
excel-ops/run action - Entry point. Launches deep-excel-research sub-agent.

Single tool entry for the skill; more workbook operations can be added later.
Loads skill body as system prompt, builds tools: list_sheets, read_structure, read_sample, fill_by_column.
Main agent invokes excel-ops.run(path, question) once; the deep-excel-research sub-agent does the rest
(search + crawl when key is URL, then LLM extract and write).
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Ensure only JSON goes to stdout (executor parses it). Redirect all logging to stderr.
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

logger = logging.getLogger(__name__)

_project_root = Path(
    os.environ.get("SOPHON_ROOT", Path(__file__).resolve().parent.parent.parent.parent.parent)
)
_scripts_dir = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from _config import SKILL_NAME, SUBAGENT_DEEP_EXCEL_RESEARCH  # type: ignore
# Load skill constants explicitly (core uses project constants)
import importlib.util
_spec = importlib.util.spec_from_file_location("excel_ops_constants", Path(__file__).resolve().parent.parent / "constants.py")
_c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_c)
DB_FILENAME = _c.DB_FILENAME  # type: ignore
from core.agent_loop import run_tool_agent  # type: ignore
from core.executor import execute_skill  # type: ignore
from core.ipc import emit_event, get_reporter  # type: ignore
from providers import get_provider  # type: ignore
from core.skill_loader import get_skill_loader  # type: ignore
from core.tool_builder import build_tools_from_skills  # type: ignore


def _resolve_params(params: dict) -> dict:
    workspace_root = Path(params.get("workspace_root") or ".").resolve()
    session_id = str(params.get("_executor_session_id") or params.get("session_id") or "default")
    user_id = str(params.get("user_id") or "default_user")
    db_path_raw = params.get("db_path")
    db_path = Path(db_path_raw) if db_path_raw else workspace_root / DB_FILENAME
    call_stack = list(params.get("_call_stack") or [])
    return {
        "workspace_root": workspace_root,
        "session_id": session_id,
        "user_id": user_id,
        "db_path": db_path,
        "call_stack": call_stack,
    }


async def _run_async(params: dict) -> dict:
    args = params.get("arguments") or params
    path = str(args.get("path", "")).strip()
    question = str(args.get("question", "")).strip()
    if not path:
        return {"error": "path is required", "observation": "", "answer": ""}
    if not question:
        question = "Enrich the workbook: use one column as search key and fill other columns from web search."

    resolved = _resolve_params(params)
    workspace_root = resolved["workspace_root"]
    session_id = resolved["session_id"]
    user_id = resolved["user_id"]
    db_path = resolved["db_path"]
    call_stack = resolved["call_stack"]

    loader = get_skill_loader(_project_root)
    skill_data = loader.get_skill(SKILL_NAME)
    if not skill_data or not skill_data.get("body"):
        return {"error": f"{SKILL_NAME} skill not found", "observation": "", "answer": ""}

    system_prompt = skill_data["body"]
    all_skills = loader.get_skills_for_session(selected_skills=[SKILL_NAME])
    skill_only = [s for s in all_skills if s.get("skill_name") == SKILL_NAME]
    tools = build_tools_from_skills(
        skill_only,
        loader,
        actions_filter={SKILL_NAME: ["list_sheets", "read_structure", "read_sample", "fill_by_column"]},
    )
    provider = get_provider()

    sub_question = f"Workbook file path (xlsx or superset): {path}\n\nUser request: {question}"
    logger.info("[%s.run] %s sub_agent_start path=%s question_preview=%s", SKILL_NAME, SUBAGENT_DEEP_EXCEL_RESEARCH, path, (question or "")[:80])

    run_id = os.environ.get("SOPHON_RUN_ID")
    agent_id = os.environ.get("SOPHON_AGENT_ID") or SUBAGENT_DEEP_EXCEL_RESEARCH

    reporter = get_reporter()
    event_sink = (lambda e: emit_event(e)) if reporter else None

    async def execute_tool(skill_name: str, action: str, arguments: dict) -> dict:
        if action == "run":
            return {"error": "Sub-agent must use list_sheets, read_structure, read_sample, or fill_by_column, not run."}
        return await execute_skill(
            skill_name=skill_name,
            action=action,
            arguments=arguments,
            workspace_root=workspace_root,
            session_id=session_id,
            user_id=user_id,
            root=_project_root,
            db_path=db_path if db_path.exists() else None,
            call_stack=call_stack,
            run_id=run_id,
            agent_id=agent_id,
            event_sink=event_sink,
        )

    summarize_guidance = (
        "Only consider the task complete when fill_by_column has been called and returned output_path. "
        "If you have not called fill_by_column yet, do NOT summarize — you must call it first."
    )
    answer, meta = await run_tool_agent(
        question=sub_question,
        provider=provider,
        tools=tools,
        system_prompt=system_prompt,
        max_rounds=10,
        execute_tool=execute_tool,
        summarize_guidance=summarize_guidance,
        required_in_observations="output_path",
    )
    logger.info("[%s.run] sub_agent_done answer_len=%d tokens=%d", SKILL_NAME, len(answer or ""), meta.get("tokens", 0))

    return {
        "answer": answer or "",
        "observation": answer or "",
        "tokens": meta.get("tokens", 0),
        "gen_ui": meta.get("gen_ui"),
    }


def main() -> None:
    params = json.loads(sys.stdin.read())
    result = asyncio.run(_run_async(params))
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
