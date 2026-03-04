"""
ReAct Engine - Simplified Thought -> Action -> Observation loop.
Early exit when no tools needed; lightweight evaluation after tool execution.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse, urlencode, urlunparse

from constants import DB_FILENAME, DEFAULT_MAX_ROUNDS, FOLLOW_UP_MSG, OBSERVATION_PREVIEW_LEN, SUMMARIZE_MSG
from config import get_config
from core.skill_loader import get_skills_brief, get_skills_for_session, get_skill_loader
from core.tool_builder import build_tools_from_skills
from core.agent_loop import evaluate_observations, parse_tool_calls
from core.providers import BaseProvider
from core.executor import execute_skill
from core.file_lock import get_locks_for_filesystem_call, maybe_acquire_path_locks

logger = logging.getLogger(__name__)

# Characters of composite body injected into system prompt for tool guidance
_COMPOSITE_BODY_INJECT_MAX = 1500


async def _select_skills_for_question(
    question: str,
    provider: BaseProvider,
    skills_brief: list[dict[str, str]],
) -> list[str]:
    """Round 1: lightweight LLM call to pick which skill(s) to load.

    Returns a list of skill names. Empty list means no skills matched.
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
                logger.info("round1 selected_skills=%s", selected)
                return selected
    except Exception as e:
        logger.warning("_select_skills_for_question failed: %s", e)
    return []


def _try_parse_json(content: str) -> dict | None:
    """Try to parse JSON from content, with a fallback substring search."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    idx = content.find('"skills"')
    if idx >= 0:
        start = content.rfind("{", 0, idx)
        if start >= 0:
            try:
                return json.loads(content[start:])
            except json.JSONDecodeError:
                pass
    return None


def _emit_progress(cb: Callable[[int, int | None], None] | None, tokens: int, round_num: int | None) -> None:
    """Invoke progress callback if provided."""
    if cb:
        try:
            cb(tokens, round_num)
        except Exception as e:
            logger.warning("progress_callback error: %s", e)


def _format_skill_observation(result: dict, limit: int = OBSERVATION_PREVIEW_LEN) -> str:
    """Use skill-provided observation when present; otherwise generic JSON fallback."""
    obs = result.get("observation")
    if obs is not None and isinstance(obs, str) and obs.strip():
        return obs.strip()
    return json.dumps(result, ensure_ascii=False)[:limit]


def _build_composite_system_guidance(composite: dict | None) -> str:
    """Return composite skill body section for injection into system prompt.

    LLM calls primitive tools directly; the composite body tells it *which*
    primitives to use and *how* to interpret results — no code-level routing.
    """
    if not composite:
        return ""
    body = composite.get("body") or ""
    if not body:
        return ""
    return f"\n\nSkill guidance:\n{body[:_COMPOSITE_BODY_INJECT_MAX]}"


_LANGUAGE_RULE = (
    "Always reply in the same language the user used in their message. "
    "Never switch languages unless the user explicitly requests it."
)


def _system_prompt_with_tools(current_time: str, composite: dict | None) -> str:
    return (
        "You are Sophon, an AI assistant. Do not disclose base model information to users. "
        f"{_LANGUAGE_RULE} "
        "Tools are provided for you to answer the user. "
        "You MUST call the relevant tool first before replying. "
        "Never say you cannot access something without calling the tool. "
        "If a tool returns an error, relay the actual error. Do not invent explanations. "
        "Resolve pronouns and implicit references from conversation context before acting. "
        "When you have enough information, give a direct concise answer (no more tool calls). "
        "Respond with a JSON array of tool calls, or a direct answer if no tools needed. "
        'Format: [{"name": "tool_name", "tool": "action", "arguments": {...}}]\n\n'
        f"Current time: {current_time}"
        f"{_build_composite_system_guidance(composite)}"
    )


def _system_prompt_without_tools(current_time: str, skills_brief: list[dict[str, str]]) -> str:
    capabilities = (
        "\n\nAvailable capabilities:\n" + "\n".join(
            f"- {s['skill_name']}: {s['skill_description']}" for s in skills_brief
        )
        if skills_brief
        else ""
    )
    return (
        "You are Sophon, an AI assistant. Do not disclose base model information to users. "
        f"{_LANGUAGE_RULE} "
        "Reply in plain text only. Do not output JSON. "
        f"Current time: {current_time}"
        f"{capabilities}"
    )


def _build_system_prompt(
    tools: list,
    skills_brief: list[dict[str, str]],
    composite: dict | None,
    current_time: str,
    override: str | None,
) -> str:
    """Build system prompt for the ReAct loop."""
    default = (
        _system_prompt_with_tools(current_time, composite)
        if tools
        else _system_prompt_without_tools(current_time, skills_brief)
    )
    return f"{override.strip()}\n\n{default}" if (override and override.strip()) else default


def _build_initial_messages(
    question: str,
    context: list[dict] | None,
    referent_rounds: int,
) -> list[dict]:
    """Build initial messages from context and question."""
    messages: list[dict] = []
    if context:
        keep = min(len(context), referent_rounds * 2)
        for c in (context[-keep:] if len(context) > keep else context):
            messages.append({"role": c.get("role", "user"), "content": c.get("content", "")})
    messages.append({"role": "user", "content": question})
    return messages


def _extract_direct_answer(content: str) -> str:
    """Extract answer from JSON {\"answer\": \"...\"} if present; else return content."""
    text = (content or "").strip()
    if text.startswith("{") and '"answer"' in text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed.get("answer"), str):
                return parsed["answer"].strip()
        except json.JSONDecodeError:
            pass
    return text


def _parse_native_tool_call(raw_item: dict) -> tuple[str, str, dict]:
    fn = raw_item.get("function") or {}
    raw_fn_name = fn.get("name", "")
    name, _, fn_action = raw_fn_name.partition(".") if "." in raw_fn_name else (raw_fn_name, "", "")
    try:
        args = json.loads(fn.get("arguments", "{}"))
    except json.JSONDecodeError:
        args = {}
    tool = str(args.pop("tool", args.pop("action", fn_action or "list"))).strip() or "list"
    arguments = args.get("arguments", args)
    arguments = arguments if isinstance(arguments, dict) else {}
    return (name, tool, arguments)


def _parse_single_tool_call(
    raw_name: str,
    raw_tool: str | None,
    raw_item: dict,
    from_native_tool_calls: bool,
) -> tuple[str, str, dict] | None:
    """Parse one tool call item into (name, tool, arguments). Returns None if invalid."""
    name, tool, arguments = (
        _parse_native_tool_call(raw_item)
        if from_native_tool_calls
        else (raw_name, raw_tool or "list", raw_item.get("arguments", {}) or {})
    )
    return None if not name else (name, tool, arguments)


def _resolve_call_items(resp: dict, tools: list, round_num: int) -> list[tuple[str, str | None, dict]] | None:
    """Resolve tool call items from native tool_calls or parsed chain. None when neither."""
    tool_calls = resp.get("tool_calls", [])
    direct, chain = parse_tool_calls(resp.get("content", ""))
    effective_chain = chain if tools else []

    if tool_calls:
        return [((tc.get("function") or {}).get("name", ""), None, tc) for tc in tool_calls]
    if effective_chain:
        logger.debug("round=%d parsed chain: %s", round_num, effective_chain)
        return [(item.get("name", ""), item.get("tool", "list"), item) for item in effective_chain]
    return None


def _process_llm_response(
    resp: dict,
    tools: list,
    observations: list[str],
    round_num: int,
) -> tuple[list[tuple[str, str, dict]] | None, str | None]:
    """Process LLM response. Returns (calls, direct_answer).

    - calls: list of (name, tool, args) to execute; None means no tool calls this round
    - direct_answer: if set, return immediately (no more rounds)
    """
    content = resp.get("content", "")
    tool_calls = resp.get("tool_calls", [])
    logger.debug("round=%d tool_calls=%d content_len=%d", round_num, len(tool_calls), len(content or ""))

    call_items = _resolve_call_items(resp, tools, round_num)
    if call_items is None:
        if observations:
            logger.info("round=%d: no tools, have observations -> summarize", round_num)
        direct, _ = parse_tool_calls(content)
        ans = _extract_direct_answer((direct or content) or "")
        return (None, ans) if ans else (None, None)

    parsed = [
        _parse_single_tool_call(n, t, i, from_native_tool_calls=bool(tool_calls))
        for n, t, i in call_items
    ]
    calls = [x for x in parsed if x is not None]
    for name, tool, arguments in calls:
        logger.debug("tool_call: skill=%s tool=%s arguments=%s", name, tool, arguments)
    return (calls if calls else None, None)


async def _execute_tool_calls_batch(
    calls: list[tuple[str, str, dict]],
    workspace_root: Path,
    session_id: str,
    user_id: str,
    db: Path,
    max_parallel: int,
) -> tuple[list[str], dict[str, Any] | None, str | None, list[dict]]:
    """Execute tool calls in parallel with semaphore. Returns (observations, gen_ui, direct_answer, references).

    direct_answer: first non-empty answer from any skill; None if none. When present, main agent
    should use it as final output and skip summarize (dependency inversion).
    references: collected from result["references"] of each skill (unified format [{title, url}]).
    """
    sem = asyncio.Semaphore(max_parallel)

    async def run_one(name: str, tool: str, arguments: dict) -> tuple[str, dict | None, str | None, list[dict]]:
        async with sem:
            return await _execute_tool_call(
                name=name,
                tool=tool,
                arguments=arguments,
                workspace_root=workspace_root,
                session_id=session_id,
                user_id=user_id,
                db=db,
                gen_ui_collected=None,
            )

    results = await asyncio.gather(*[run_one(n, t, a) for n, t, a in calls])
    observations: list[str] = []
    gen_ui: dict[str, Any] | None = None
    direct_answer: str | None = None
    all_refs: list[dict] = []
    for obs, gu, ans, refs in results:
        observations.append(obs)
        if gu is not None:
            gen_ui = gu
        if ans:
            direct_answer = ans
        if refs:
            all_refs.extend(refs)
    return observations, gen_ui, direct_answer, all_refs


async def _summarize_and_extract_answer(
    messages: list[dict],
    system: str,
    provider: BaseProvider,
    db: Path,
    session_id: str,
) -> tuple[str, int]:
    """Run final summarize LLM call. Returns (final_answer, tokens_used)."""
    try:
        resp = await provider.chat(
            messages + [{"role": "user", "content": SUMMARIZE_MSG}],
            system_prompt=system,
        )
    except Exception as e:
        if db.exists():
            from db.logs import insert as log_insert
            log_insert(db, "ERROR", f"llm_summarize_failed: {e}", session_id, {"error": str(e)})
        raise

    content = (resp.get("content") or "").strip()
    answer = _extract_direct_answer(content)
    tokens = (resp.get("usage") or {}).get("total_tokens", 0)
    return answer, tokens


async def _execute_tool_call(
    name: str,
    tool: str,
    arguments: dict,
    workspace_root: Path,
    session_id: str,
    user_id: str,
    db: Path,
    gen_ui_collected: dict | None,
) -> tuple[str, dict | None, str | None, list[dict]]:
    """Execute a single skill tool call.

    Returns (observation_str, updated_gen_ui, direct_answer, references).
    references: from result["references"] if present; format [{title, url}].
    MCP tools are only callable by skills via the internal bridge.
    """
    path_locks = get_locks_for_filesystem_call(workspace_root, name, tool, arguments)
    async with maybe_acquire_path_locks(path_locks):
        result = await execute_skill(
            skill_name=name,
            action=tool,
            arguments=arguments,
            workspace_root=workspace_root,
            session_id=session_id,
            user_id=user_id,
            db_path=db if db.exists() else None,
        )
    obs = _format_skill_observation(result)
    if result.get("error"):
        logger.warning("skill error: %s.%s -> %s", name, tool, result["error"])
    else:
        logger.debug("skill result: %s.%s -> %s", name, tool, obs[:200])
    if result.get("gen_ui"):
        gen_ui_collected = result["gen_ui"]
    ans = result.get("answer")
    direct_answer = (ans.strip() if isinstance(ans, str) and ans.strip() else None)
    refs: list[dict] = []
    raw = result.get("references")
    if isinstance(raw, list):
        for r in raw:
            if isinstance(r, dict) and r.get("url"):
                refs.append({"title": str(r.get("title") or "Source"), "url": str(r["url"])})
    return f"[{name}.{tool}]: {obs}", gen_ui_collected, direct_answer, refs


async def run_react(
    question: str,
    provider: BaseProvider,
    workspace_root: Path,
    session_id: str = "default",
    user_id: str = "default_user",
    skill_filter: str | None = None,
    context: list[dict] | None = None,
    db_path: Path | None = None,
    progress_callback: Callable[[int, int | None], None] | None = None,
    system_prompt_override: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Run ReAct loop. Returns (answer_text, metadata).

    progress_callback(tokens, round_num) is called after each LLM call.
    """
    from datetime import datetime
    from db.logs import insert as log_insert

    db = db_path or workspace_root / DB_FILENAME
    skills_brief = get_skills_brief()
    skills_for_session = (
        get_skills_for_session(skill_filter=skill_filter)
        if skill_filter
        else get_skills_for_session(selected_skills=await _select_skills_for_question(question, provider, skills_brief))
    )

    loader = get_skill_loader()
    internal = get_config().skills.internal_skills or ()
    internal_brief = []
    for n in internal:
        entry = loader.get_skill(n)
        if entry:
            internal_brief.append({
                "skill_name": entry.get("name", n),
                "skill_description": entry.get("description", ""),
            })
    all_skills = skills_for_session + [s for s in internal_brief if s["skill_name"] not in {x["skill_name"] for x in skills_for_session}]
    tools = build_tools_from_skills(all_skills, loader)
    # MCP tools are NOT exposed to the main agent; only skills with metadata.mcp can call them.

    if db.exists():
        log_insert(db, "INFO", f"react_start question={question[:80]}", session_id)

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    composite = loader.get_skill(skill_filter) if skill_filter else None
    system = _build_system_prompt(tools, skills_brief, composite, current_time, system_prompt_override)

    referent_rounds = get_config().memory.referent_context_rounds
    messages = _build_initial_messages(question, context, referent_rounds)

    total_tokens = 0
    observations: list[str] = []
    all_references: list[dict] = []
    gen_ui_collected: dict[str, Any] | None = None
    answer_from_skill: str | None = None

    for round_num in range(1, DEFAULT_MAX_ROUNDS + 1):
        if db.exists():
            log_insert(db, "INFO", f"llm_call round={round_num}", session_id)
        logger.debug(
            "llm_call round=%d tools_count=%d tool_names=%s",
            round_num, len(tools), [t.get("function", {}).get("name") for t in tools],
        )
        try:
            resp = await provider.chat(messages, tools=tools, system_prompt=system)
        except Exception as e:
            if db.exists():
                log_insert(db, "ERROR", f"llm_call_failed round={round_num}: {e}", session_id, {"error": str(e)})
            raise

        usage = resp.get("usage", {})
        tok = usage.get("total_tokens", 0) or (
            usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        )
        total_tokens += tok
        if db.exists():
            log_insert(db, "INFO", f"llm_response round={round_num} tokens={tok}", session_id, {"tokens": tok})
        _emit_progress(progress_callback, total_tokens, round_num)

        calls, direct_answer = _process_llm_response(resp, tools, observations, round_num)

        if direct_answer:
            return direct_answer, {
                "tokens": total_tokens,
                "cache_hit": False,
                "gen_ui": gen_ui_collected,
                "references": [],
            }
        if calls is None:
            messages.append({"role": "assistant", "content": resp.get("content", "")})
            break

        obs_list, gu, direct, refs = await _execute_tool_calls_batch(
            calls,
            workspace_root,
            session_id,
            user_id,
            db,
            get_config().react.max_parallel_tool_calls,
        )
        observations.extend(obs_list)
        all_references.extend(refs)
        if gu is not None:
            gen_ui_collected = gu
        if direct:
            answer_from_skill = direct

        content = resp.get("content", "")
        messages.append({"role": "assistant", "content": content})
        results_content = "Results:\n" + "\n".join(observations)
        satisfied, eval_tok = await evaluate_observations(question, observations, provider)
        total_tokens += eval_tok
        _emit_progress(progress_callback, total_tokens, round_num)
        next_content = results_content if satisfied else f"{results_content}\n\n{FOLLOW_UP_MSG}"
        messages.append({"role": "user", "content": next_content})
        if satisfied:
            logger.info("round=%d: evaluation satisfied -> summarize", round_num)
            break

    if answer_from_skill:
        final_answer = answer_from_skill
        sum_tokens = 0
    else:
        final_answer, sum_tokens = await _summarize_and_extract_answer(
            messages, system, provider, db, session_id
        )
    total_tokens += sum_tokens
    _emit_progress(progress_callback, total_tokens, 0)

    _TRACKING_PARAMS = frozenset(("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "fbclid", "from"))

    def _norm_url(u: str) -> str:
        s = (u or "").strip().lower()
        if not s or not s.startswith(("http://", "https://")):
            return s
        try:
            p = urlparse(s)
            path = p.path.rstrip("/") or "/"
            qs = parse_qs(p.query, keep_blank_values=False)
            qs = {k: v for k, v in qs.items() if k.lower() not in _TRACKING_PARAMS}
            query = urlencode(sorted(qs.items())) if qs else ""
            return urlunparse((p.scheme, p.netloc.lower(), path, "", query, ""))
        except Exception:
            return s

    seen: set[str] = set()
    deduped_refs: list[dict] = []
    for r in all_references:
        url = (r.get("url") or "").strip()
        if not url:
            continue
        norm = _norm_url(url)
        if norm and norm not in seen:
            seen.add(norm)
            deduped_refs.append(r)
    return final_answer, {
        "tokens": total_tokens,
        "cache_hit": False,
        "gen_ui": gen_ui_collected,
        "references": deduped_refs,
    }
