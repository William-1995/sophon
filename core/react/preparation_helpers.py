"""
ReAct Preparation - Setup and initialization for ReAct runs.

Handles skill selection, tool building, system prompt construction,
and initial context preparation.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from config import get_config
from constants import (
    CAPABILITIES_SKILL_NAME,
    DB_FILENAME
)
from core.skill_loader import get_skill_loader, get_skills_brief, get_skills_for_session
from core.skill_loader.capability_resolver import filter_runtime_skills, resolve_skills_for_text
from core.execution.builder import build_compact_tools_from_full, build_tools_from_skills
from providers import BaseProvider
from core.react.context import ImmutableRunContext, MutableRunState, build_initial_messages
from core.react.skill_selection import select_skills_for_question
from core.react.system_prompt_builder import build_system_prompt
from core.react.question_heuristics import question_suggests_multi_part
from core.react.utils import _COMPOSITE_BODY_INJECT_MAX
from core.task_plan import (
    TASK_PLAN_ENTRY_ACTION,
    TASK_PLAN_SKILL_NAME,
    build_task_plan_openai_tool,
)

logger = logging.getLogger(__name__)

# HITL: synthetic tool name for human-in-the-loop


HITL_TOOL_NAME = "request_human_decision"


def _include_capabilities_internal_tool(
    selected: list[str],
    skill_filter: str | None,
) -> bool:
    """Merge internal capabilities skill only when session scope includes it (filter or round-1 selection).

    No text heuristics: orchestration does not infer user intent from wording.
    """
    if skill_filter == CAPABILITIES_SKILL_NAME:
        return True
    if skill_filter and skill_filter != CAPABILITIES_SKILL_NAME:
        return False
    return CAPABILITIES_SKILL_NAME in selected


def build_hitl_tool() -> dict:
    """Build OpenAI-format tool for request_human_decision (HITL).

    Returns:
        OpenAI-format tool definition dict.
    """
    return {
        "type": "function",
        "function": {
            "name": HITL_TOOL_NAME,
            "description": (
                "Optional LLM-initiated choice modal (off by default in server config). "
                "Do not use for routine execution or delete confirmation—filesystem delete uses its own confirm flow. "
                "If enabled, use only when the task truly cannot continue without a user choice. "
                "Execution suspends until the user picks an option."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Question or context for the user"},
                    "choices": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Options the user can pick",
                    },
                },
                "required": ["message", "choices"],
            },
        },
    }


async def inject_file_contents(
    question: str,
    workspace_root: Path,
    db_path: Path | None,
) -> tuple[str, list[dict]]:
    """Detect @filename in question. No content injection—path stays in question.

    Main agent selects the right skill (pdf, word, filesystem) and passes path
    in tool arguments. The skill receives workspace_root + path and reads the file.
    """
    file_pattern = r'@([^\s]+)'
    matches = list(re.finditer(file_pattern, question))
    if not matches:
        return question, []

    modified_question = question
    for match in matches:
        filename = match.group(1)
        modified_question = modified_question.replace(f"@{filename}", filename)

    return modified_question, []

async def _build_react_tools_and_skills(
    question: str,
    provider: BaseProvider,
    skill_filter: str | None,
    decision_waiter: Any,
    run_id: str | None,
    fixed_selected_skills: list[str] | None = None,
) -> tuple[list, list[dict], Any, bool, int]:
    """Resolve skills and build tools. Returns (tools, skills_brief, loader, multi_part, select_tokens)."""
    skills_brief = get_skills_brief()
    selected, skills_for_session, select_tokens, multi_part = await _resolve_react_skills(
        question, provider, skill_filter, skills_brief, fixed_selected_skills
    )
    _log_react_skills_selected(selected, skills_for_session, skill_filter)
    loader = get_skill_loader()
    all_skills = _build_all_skills_for_react(
        skills_for_session,
        loader,
        selected_skill_names=selected,
        skill_filter=skill_filter,
    )
    actions_filter = _build_react_actions_filter(all_skills, loader)
    tools = _build_react_tools(
        all_skills, loader, actions_filter, decision_waiter, run_id
    )
    _log_react_tools(tools)
    return tools, skills_brief, loader, multi_part, select_tokens


async def prepare_react_run(
    question: str,
    provider: BaseProvider,
    workspace_root: Path,
    session_id: str,
    user_id: str,
    skill_filter: str | None,
    context: list[dict] | None,
    db_path: Path | None,
    system_prompt_override: str | None,
    resume_checkpoint: dict[str, Any] | None,
    run_id: str | None,
    decision_waiter: Any,
    fixed_selected_skills: list[str] | None = None,
) -> tuple[ImmutableRunContext, MutableRunState]:
    """Build context and initial state for a ReAct run.

    Args:
        question: Original user question.
        provider: LLM provider.
        workspace_root: Workspace root path.
        session_id: Session identifier.
        user_id: User identifier.
        skill_filter: Optional skill to restrict to (single skill; takes precedence).
        fixed_selected_skills: When set (and skill_filter is None), skip round-1 skill
            selection and load these primary skills plus declared dependencies.
        context: Optional conversation context.
        db_path: Optional database path.
        system_prompt_override: Optional system prompt override.
        resume_checkpoint: Optional checkpoint to resume from.
        run_id: Optional run identifier.
        decision_waiter: HITL decision waiter callback.

    Returns:
        Tuple of (immutable context, mutable state).
    """
    from db.logs import insert as log_insert

    db = db_path or workspace_root / DB_FILENAME
    modified_question, file_context = await inject_file_contents(
        question, workspace_root, db_path
    )
    if file_context:
        logger.info("Auto-injected %d file(s) from @references", len(file_context))

    (
        tools,
        skills_brief,
        loader,
        multi_part,
        select_tokens,
    ) = await _build_react_tools_and_skills(
        question, provider, skill_filter, decision_waiter, run_id, fixed_selected_skills
    )

    if db.exists():
        log_insert(db, "INFO", f"react_start question={modified_question}", session_id)

    state = MutableRunState()
    state.total_tokens = select_tokens
    if select_tokens > 0 and db.exists():
        log_insert(db, "INFO", f"tokens step=select_skills tokens={select_tokens}", session_id, {"step": "select_skills", "tokens": select_tokens})
        from db.metrics import insert as metrics_insert
        metrics_insert(db, "llm_tokens", float(select_tokens), tags={"step": "select_skills", "session_id": session_id, "run_id": run_id or ""})

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    composite = loader.get_skill(skill_filter) if skill_filter else None
    system = build_system_prompt(
        tools,
        composite,
        current_time,
        system_prompt_override,
        modified_question,
        composite_body_max=_COMPOSITE_BODY_INJECT_MAX,
        multi_part=multi_part,
    )
    referent_rounds = get_config().memory.referent_context_rounds
    messages = build_initial_messages(
        modified_question, context, referent_rounds, file_context
    )
    start_round, modified_question = _apply_resume_checkpoint(
        resume_checkpoint, messages, state, modified_question
    )
    compact_tools = build_compact_tools_from_full(tools)
    ctx = ImmutableRunContext(
        db=db,
        modified_question=modified_question,
        tools=tools,
        compact_tools=compact_tools,
        system=system,
        messages=messages,
        start_round=start_round,
        session_id=session_id,
        user_id=user_id,
        workspace_root=workspace_root,
        question=question,
        multi_part=multi_part,
        run_id=run_id,
    )
    return ctx, state


async def _resolve_react_skills(
    question: str,
    provider: BaseProvider,
    skill_filter: str | None,
    skills_brief: list[dict[str, str]],
    fixed_selected_skills: list[str] | None = None,
) -> tuple[list[str], list[dict], int, bool]:
    """Resolve selected skill names, skills_for_session, tokens, and multi_step.

    Returns:
        Tuple of (selected, skills_for_session, select_skills_tokens, multi_part).
        multi_part: True when skill picker set multi_step (stricter prompt). Todos is no longer auto-injected.
    """
    if skill_filter:
        selected = list(filter_runtime_skills([skill_filter])) or [skill_filter]
        select_tokens = 0
        multi_part = question_suggests_multi_part(question)
        skills_for_session = get_skills_for_session(skill_filter=selected[0])
    elif fixed_selected_skills:
        selected = list(filter_runtime_skills(fixed_selected_skills))
        select_tokens = 0
        multi_part = True
        skills_for_session = get_skills_for_session(selected_skills=selected)
    else:
        selected, select_tokens, multi_part = await select_skills_for_question(
            question, provider, skills_brief
        )
        if not selected:
            # Shared fallback path: use the same runtime capability matching used by workflow.
            selected = list(resolve_skills_for_text(question, max_skills=8))
            if selected and not multi_part:
                multi_part = question_suggests_multi_part(question)
        skills_for_session = get_skills_for_session(selected_skills=selected)
    return selected, skills_for_session, select_tokens, multi_part


def _log_react_skills_selected(
    selected: list[str],
    skills_for_session: list[dict],
    skill_filter: str | None,
) -> None:
    """Log selected skills and skills_for_session."""
    exposed = list(get_config().skills.exposed_skills) if get_config().skills.exposed_skills else []
    logger.debug("[react] skill_filter=%s exposed_skills=%s", skill_filter, exposed)
    if skill_filter:
        logger.debug("[react] skill_filter=%s (skip round1 select)", skill_filter)
    sf = [s.get("skill_name", s.get("name", "")) for s in skills_for_session]
    logger.info("[react] selected_skills=%s skills_for_session=%s", selected, sf)


def _build_all_skills_for_react(
    skills_for_session: list[dict],
    loader: Any,
    selected_skill_names: list[str] | None = None,
    skill_filter: str | None = None,
) -> list[dict]:
    """Merge session skills with internal skills (no duplicates).

    Internal `capabilities` is omitted unless filter or round-1 selection includes it.
    """
    internal = get_config().skills.internal_skills or ()
    selected_skill_names = selected_skill_names or []
    include_cap = _include_capabilities_internal_tool(selected_skill_names, skill_filter)
    internal_brief = []
    for n in internal:
        if n == CAPABILITIES_SKILL_NAME and not include_cap:
            continue
        entry = loader.get_skill(n)
        if entry:
            internal_brief.append({
                "skill_name": entry.get("name", n),
                "skill_description": entry.get("description", ""),
            })
    return skills_for_session + [
        s for s in internal_brief
        if s["skill_name"] not in {x["skill_name"] for x in skills_for_session}
    ]


def _build_react_actions_filter(all_skills: list[dict], loader: Any) -> dict[str, list[str]]:
    """Build skill name -> [entry_action] from skills that have entry_action."""
    actions_filter: dict[str, list[str]] = {}
    for s in all_skills:
        name = s.get("skill_name", s.get("name", ""))
        if not name:
            continue
        full = loader.get_skill(name)
        if full and full.get("entry_action"):
            actions_filter[name] = [full["entry_action"]]
    skill_names = {x.get("skill_name", x.get("name", "")) for x in all_skills}
    if TASK_PLAN_SKILL_NAME in skill_names and TASK_PLAN_SKILL_NAME not in actions_filter:
        actions_filter[TASK_PLAN_SKILL_NAME] = [TASK_PLAN_ENTRY_ACTION]
    return actions_filter


def _build_react_tools(
    all_skills: list[dict],
    loader: Any,
    actions_filter: dict[str, list[str]],
    decision_waiter: Any,
    run_id: str | None,
) -> list:
    """Build tool list from skills; append built-in task_plan + HITL when enabled."""
    disk_skills = [s for s in all_skills if s.get("skill_name", s.get("name", "")) != TASK_PLAN_SKILL_NAME]
    tools = build_tools_from_skills(
        disk_skills, loader,
        actions_filter=actions_filter if actions_filter else None,
    )
    if any(s.get("skill_name", s.get("name", "")) == TASK_PLAN_SKILL_NAME for s in all_skills):
        tools.append(build_task_plan_openai_tool())
    if get_config().react.hitl_enabled and decision_waiter and run_id:
        tools.append(build_hitl_tool())
    return tools


def _log_react_tools(tools: list) -> None:
    """Log tool count and names."""
    tool_names = [t.get("function", {}).get("name") for t in tools]
    logger.debug("[react] tools_count=%d tool_names=%s", len(tools), tool_names)


def _apply_resume_checkpoint(
    resume_checkpoint: dict[str, Any] | None,
    messages: list[dict],
    state: MutableRunState,
    modified_question: str,
) -> tuple[int, str]:
    """Apply resume checkpoint to messages and state.

    Returns:
        Tuple of (start_round, modified_question).
    """
    start_round = 1
    if not resume_checkpoint:
        return start_round, modified_question
    messages[:] = list(resume_checkpoint.get("messages") or [])
    state.observations = list(resume_checkpoint.get("observations") or [])
    state.total_tokens = int(resume_checkpoint.get("total_tokens") or 0)
    start_round = int(resume_checkpoint.get("round_num") or 0) + 1
    if resume_checkpoint.get("question"):
        modified_question = str(resume_checkpoint["question"])
    logger.info(
        "[react] resume from checkpoint round=%d obs_count=%d",
        start_round - 1, len(state.observations),
    )
    return start_round, modified_question
