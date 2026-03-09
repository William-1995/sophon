"""
ReAct Preparation - Setup and initialization for ReAct runs.

Handles skill selection, tool building, system prompt construction,
and initial context preparation.
"""

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from config import get_config
from constants import DB_FILENAME, FILE_INJECTION_MAX_LEN
from core.agent_loop import parse_tool_calls
from core.executor import execute_skill
from core.file_lock import get_locks_for_filesystem_call, maybe_acquire_path_locks
from core.skill_loader import get_skill_loader, get_skills_brief, get_skills_for_session
from core.tool_builder import build_tools_from_skills
from providers import BaseProvider

from core.react.context import ImmutableRunContext, MutableRunState

logger = logging.getLogger(__name__)

# HITL: synthetic tool name for human-in-the-loop
HITL_TOOL_NAME = "request_human_decision"


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
                "When you need human input to proceed (e.g. ambiguous data, conflicting options), "
                "call this tool. Execution suspends until the user chooses. Use sparingly."
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


async def select_skills_for_question(
    question: str,
    provider: BaseProvider,
    skills_brief: list[dict[str, str]],
) -> list[str]:
    """Round 1: lightweight LLM call to pick which skill(s) to load.

    Args:
        question: User question to analyze.
        provider: LLM provider for selection inference.
        skills_brief: List of available skills with names and descriptions.

    Returns:
        List of selected skill names. Empty list means no skills matched.
    """
    if not skills_brief:
        return []
    skill_list = "\n".join(
        f"- {s['skill_name']}: {s['skill_description'][:180]}..." for s in skills_brief
    )
    sys_prompt = (
        "Pick ALL skills needed to fully answer every part of the question. "
        'Reply with JSON only: {"skills": ["skill_name1", "skill_name2"]}. '
        "Use exact skill_name from the list. For compound questions, select multiple skills."
    )
    user_prompt = f"Question: {question}\n\nAvailable skills:\n{skill_list}\n\nWhich skill(s)? JSON only."
    try:
        resp = await provider.chat(
            [{"role": "user", "content": user_prompt}],
            tools=None,
            system_prompt=sys_prompt,
        )
        content = (resp.get("content") or "").strip()
        if "```" in content:
            for part in content.split("```"):
                if "skills" in part and "{" in part:
                    content = part.replace("json", "").strip()
                    break
        data = _try_parse_json(content)
        if data and isinstance(data.get("skills"), list):
            valid = {s["skill_name"] for s in skills_brief}
            selected = [x for x in data["skills"] if isinstance(x, str) and x in valid]
            if selected:
                logger.info("[react] selected_skills=%s", selected)
                print(f"[react] selected_skills={selected}", file=sys.stderr, flush=True)
                return selected
    except Exception as e:
        logger.warning("[react] _select_skills_for_question failed: %s", e)
    logger.info("[react] selected_skills=[] (none matched)")
    print("[react] selected_skills=[] (none matched)", file=sys.stderr, flush=True)
    return []


def _try_parse_json(content: str) -> dict | None:
    """Try to parse JSON from content, with a fallback substring search.

    Args:
        content: Text that may contain JSON.

    Returns:
        Parsed dict or None if parsing fails.
    """
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    idx = content.find('"skills"')
    if idx >= 0:
        brace_start = content.rfind("{", 0, idx)
        brace_end = content.find("}", idx)
        if brace_start >= 0 and brace_end >= 0:
            try:
                return json.loads(content[brace_start : brace_end + 1])
            except json.JSONDecodeError:
                pass
    return None


def _build_user_response_context(question: str) -> dict:
    """Infer user's language and format from the question for response guidance.

    Args:
        question: User's question text.

    Returns:
        Dict with response guidance parameters.
    """
    q = (question or "").strip()
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", q))
    detected_lang = "zh" if has_cjk else "en"
    return {
        "language": detected_lang,
        "tone": "helpful and concise",
        "format": "plain text only, no markdown code blocks unless explicitly requested",
    }


def _system_prompt_with_tools(
    current_time: str,
    composite: dict | None,
    user_response_context: dict,
) -> str:
    """Build base system prompt when tools are available.

    Args:
        current_time: Current timestamp string.
        composite: Optional composite skill definition.
        user_response_context: User language/format preferences.

    Returns:
        System prompt string.
    """
    base = (
        "You are Sophon, an AI assistant. Do not disclose base model information to users. "
        "Reply in plain text only. Do not output JSON. "
        f"Current time: {current_time}"
    )
    if composite:
        body = composite.get("body", "")
        if body:
            trimmed = body[:_COMPOSITE_BODY_INJECT_MAX]
            if len(body) > _COMPOSITE_BODY_INJECT_MAX:
                trimmed += "\n...[truncated]"
            base += f"\n\nSkill guidance:\n{trimmed}"
    return f"{base}\n\nResponse context (follow strictly): {json.dumps(user_response_context)}"


def _system_prompt_without_tools(
    current_time: str,
    skills_brief: list[dict[str, str]],
    user_response_context: dict,
) -> str:
    """Build base system prompt when no tools are available.

    Args:
        current_time: Current timestamp string.
        skills_brief: List of available skills for context.
        user_response_context: User language/format preferences.

    Returns:
        System prompt string.
    """
    capabilities = (
        "\n\nAvailable capabilities:\n" + "\n".join(
            f"- {s['skill_name']}: {s['skill_description']}" for s in skills_brief
        )
        if skills_brief
        else ""
    )
    ctx_block = f"\n\nResponse context (follow strictly): {json.dumps(user_response_context)}"
    return (
        "You are Sophon, an AI assistant. Do not disclose base model information to users. "
        "Reply in plain text only. Do not output JSON. "
        f"Current time: {current_time}"
        f"{capabilities}"
        f"{ctx_block}"
    )


def build_system_prompt(
    tools: list,
    skills_brief: list[dict[str, str]],
    composite: dict | None,
    current_time: str,
    override: str | None,
    question: str,
) -> str:
    """Build system prompt for the ReAct loop.

    Injects user_response_context object so LLM replies in the user's language.

    Args:
        tools: List of available tools.
        skills_brief: List of skill briefs for context.
        composite: Optional composite skill definition.
        current_time: Current timestamp.
        override: Optional system prompt override.
        question: User question for language detection.

    Returns:
        Complete system prompt string.
    """
    user_response_context = _build_user_response_context(question)
    default = (
        _system_prompt_with_tools(current_time, composite, user_response_context)
        if tools
        else _system_prompt_without_tools(current_time, skills_brief, user_response_context)
    )
    return f"{override.strip()}\n\n{default}" if (override and override.strip()) else default


async def inject_file_contents(
    question: str,
    workspace_root: Path,
    db_path: Path | None,
) -> tuple[str, list[dict]]:
    """Detect @filename in question and auto-read file contents.

    Args:
        question: User question that may contain @filename references.
        workspace_root: Root path for resolving relative paths.
        db_path: Optional database path for skill execution.

    Returns:
        Tuple of (modified_question, file_context_messages).
    """
    file_pattern = r'@([^\s]+)'
    matches = list(re.finditer(file_pattern, question))

    if not matches:
        return question, []

    file_contexts = []
    files_read = []

    for match in matches:
        filename = match.group(1)
        try:
            result = await execute_skill(
                skill_name="filesystem",
                action="read",
                arguments={"path": filename},
                workspace_root=workspace_root,
                session_id="file_injection",
                user_id="system",
                db_path=db_path if db_path and db_path.exists() else None,
            )

            if result.get("error"):
                continue

            content = result.get("content", "")
            if not content:
                continue

            max_len = FILE_INJECTION_MAX_LEN
            truncated = len(content) > max_len
            display_content = content[:max_len] + ("\n... (truncated)" if truncated else "")

            file_contexts.append({
                "filename": filename,
                "content": display_content,
            })
            files_read.append(filename)

        except Exception as e:
            logger.debug("Failed to auto-read @file %s: %s", filename, e)
            continue

    if not file_contexts:
        return question, []

    context_messages = []
    for fc in file_contexts:
        context_messages.append({
            "role": "system",
            "content": f"File '{fc['filename']}' content:\n```\n{fc['content']}\n```",
        })

    modified_question = question
    for filename in files_read:
        modified_question = modified_question.replace(f"@{filename}", filename)

    return modified_question, context_messages


def build_initial_messages(
    question: str,
    context: list[dict] | None,
    referent_rounds: int,
    file_context: list[dict] | None = None,
) -> list[dict]:
    """Build initial messages from context, file context, and question.

    Args:
        question: User question.
        context: Optional conversation context.
        referent_rounds: Number of rounds to keep in context.
        file_context: Optional file context messages.

    Returns:
        List of initial messages for the conversation.
    """
    messages: list[dict] = []

    if file_context:
        messages.extend(file_context)

    if context:
        keep = min(len(context), referent_rounds * 2)
        for c in (context[-keep:] if len(context) > keep else context):
            messages.append({"role": c.get("role", "user"), "content": c.get("content", "")})

    messages.append({"role": "user", "content": question})
    return messages


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
) -> tuple[ImmutableRunContext, MutableRunState]:
    """Build context and initial state for a ReAct run.

    Args:
        question: Original user question.
        provider: LLM provider.
        workspace_root: Workspace root path.
        session_id: Session identifier.
        user_id: User identifier.
        skill_filter: Optional skill to restrict to.
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

    skills_brief = get_skills_brief()
    selected, skills_for_session = await _resolve_react_skills(
        question, provider, skill_filter, skills_brief
    )
    _log_react_skills_selected(selected, skills_for_session, skill_filter)

    loader = get_skill_loader()
    all_skills = _build_all_skills_for_react(skills_for_session, loader)
    actions_filter = _build_react_actions_filter(all_skills, loader)
    tools = _build_react_tools(
        all_skills, loader, actions_filter, decision_waiter, run_id
    )
    _log_react_tools(tools)

    if db.exists():
        log_insert(db, "INFO", f"react_start question={modified_question}", session_id)

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    composite = loader.get_skill(skill_filter) if skill_filter else None
    system = build_system_prompt(
        tools, skills_brief, composite, current_time,
        system_prompt_override, modified_question,
    )
    referent_rounds = get_config().memory.referent_context_rounds
    messages = build_initial_messages(
        modified_question, context, referent_rounds, file_context
    )
    state = MutableRunState()
    start_round, modified_question = _apply_resume_checkpoint(
        resume_checkpoint, messages, state, modified_question
    )

    ctx = ImmutableRunContext(
        db=db,
        modified_question=modified_question,
        tools=tools,
        system=system,
        messages=messages,
        start_round=start_round,
        session_id=session_id,
        user_id=user_id,
        workspace_root=workspace_root,
        question=question,
    )
    return ctx, state


async def _resolve_react_skills(
    question: str,
    provider: BaseProvider,
    skill_filter: str | None,
    skills_brief: list[dict[str, str]],
) -> tuple[list[str], list[dict]]:
    """Resolve selected skill names and skills_for_session list.

    Returns:
        Tuple of (selected, skills_for_session).
    """
    if skill_filter:
        selected = [skill_filter]
    else:
        selected = await select_skills_for_question(question, provider, skills_brief)
    skills_for_session = (
        get_skills_for_session(skill_filter=skill_filter)
        if skill_filter
        else get_skills_for_session(selected_skills=selected)
    )
    return selected, skills_for_session


def _log_react_skills_selected(
    selected: list[str],
    skills_for_session: list[dict],
    skill_filter: str | None,
) -> None:
    """Log and stderr-print selected skills and skills_for_session."""
    import sys
    exposed = list(get_config().skills.exposed_skills) if get_config().skills.exposed_skills else []
    print(f"[react] skill_filter={skill_filter} exposed_skills={exposed}", flush=True)
    if skill_filter:
        print(f"[react] skill_filter={skill_filter} (skip round1 select)", flush=True)
    sf = [s.get("skill_name", s.get("name", "")) for s in skills_for_session]
    logger.info("[react] selected_skills=%s skills_for_session=%s", selected, sf)
    print(f"[react] selected_skills={selected} skills_for_session={sf}", flush=True)


def _build_all_skills_for_react(
    skills_for_session: list[dict],
    loader: Any,
) -> list[dict]:
    """Merge session skills with internal skills (no duplicates)."""
    internal = get_config().skills.internal_skills or ()
    internal_brief = []
    for n in internal:
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
    return actions_filter


def _build_react_tools(
    all_skills: list[dict],
    loader: Any,
    actions_filter: dict[str, list[str]],
    decision_waiter: Any,
    run_id: str | None,
) -> list:
    """Build tool list from skills; append HITL tool when enabled."""
    tools = build_tools_from_skills(
        all_skills, loader,
        actions_filter=actions_filter if actions_filter else None,
    )
    if get_config().react.hitl_enabled and decision_waiter and run_id:
        tools.append(build_hitl_tool())
    return tools


def _log_react_tools(tools: list) -> None:
    """Log and stderr-print tool count and names."""
    import sys
    tool_names = [t.get("function", {}).get("name") for t in tools]
    logger.info("[react] tools_count=%d tool_names=%s", len(tools), tool_names)
    print(f"[react] tools_count={len(tools)} tool_names={tool_names}", flush=True)


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
