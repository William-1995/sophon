"""
ReAct Engine - Simplified Thought -> Action -> Observation loop.
Early exit when no tools needed; lightweight evaluation after tool execution.
"""

import json
import logging
from pathlib import Path
from typing import Any, Callable

from constants import DB_FILENAME, DEFAULT_MAX_ROUNDS, OBSERVATION_PREVIEW_LEN
from config import get_config
from core.skill_loader import get_skills_brief, get_skills_for_session, get_skill_loader
from core.tool_builder import build_tools_from_skills
from core.agent_loop import evaluate_observations, parse_tool_calls
from core.providers import BaseProvider
from core.executor import execute_skill
from mcp_client.manager import get_mcp_manager

logger = logging.getLogger(__name__)


async def _select_skills_for_question(
    question: str,
    provider: BaseProvider,
    skills_brief: list[dict[str, str]],
) -> list[str]:
    """
    Round 1: lightweight LLM call to pick which skill(s) apply to the user question.
    Returns list of skill names to load (with their deps in round 2).
    """
    if not skills_brief:
        return []
    skill_list = "\n".join(f"- {s['skill_name']}: {s['skill_description'][:120]}..." for s in skills_brief)
    sys_prompt = (
        "Pick which skill(s) are needed to answer the user. "
        "Reply with JSON only: {\"skills\": [\"skill_name1\", \"skill_name2\"]}. "
        "Use exact skill_name from the list. Pick the minimum set."
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
                print(f"[react] round1 selected_skills={selected}")
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
    """
    Format a skill result dict as an observation string.
    For deep-research results (report + sources), preserve full content instead of
    truncating raw JSON.
    """
    if "report" in result and "sources" in result:
        parts: list[str] = []
        if result.get("summary"):
            parts.append(f"SUMMARY: {result['summary']}")
        parts.append(f"REPORT:\n{result.get('report', '')}")
        sources = result.get("sources", [])
        if sources:
            src_lines = [f"SOURCES ({len(sources)} total):"]
            for i, src in enumerate(sources, 1):
                title = src.get("title") or src.get("url", "")
                src_lines.append(f"  {i}. {title} — {src.get('url', '')}")
            parts.append("\n".join(src_lines))
        combined = "\n\n".join(parts)
        return combined[:max(limit * 8, 6000)]
    return json.dumps(result, ensure_ascii=False)[:limit]


def _resolve_composite_call(
    skill_name: str,
    action: str,
    arguments: dict,
    loader: Any,
) -> tuple[str, str, dict]:
    """
    Route composite+dependency calls to primitive.
    E.g. troubleshoot + log-analyze -> log-analyze + query.
    Returns (resolved_skill, resolved_action, resolved_arguments).
    """
    skill_data = loader.get_skill(skill_name)
    if not skill_data:
        return skill_name, action, arguments
    deps = skill_data.get("dependencies") or []
    if not deps or action not in deps:
        return skill_name, action, arguments
    primitive = action
    args = dict(arguments)
    sub_action = args.pop("tool", None) or args.pop("action", None)
    sub_action = str(sub_action).strip() if sub_action else ""
    if not sub_action:
        if primitive == "metrics" and any(k in args for k in ("value", "timestamp")):
            sub_action = "write"
        elif primitive == "metrics" and any(k in args for k in ("metric_name", "since", "until")):
            sub_action = "query"
        elif any(k in args for k in ("level", "keyword", "regex", "session_id", "span_id", "trace_id")):
            sub_action = "query"
        elif any(k in args for k in ("since", "until")):
            sub_action = "analyze"
        else:
            sub_action = "list"
    logger.info("[react] route composite %s.%s -> %s.%s", skill_name, action, primitive, sub_action)
    return primitive, sub_action, args


async def _execute_tool_call(
    name: str,
    tool: str,
    arguments: dict,
    loader: Any,
    mcp_manager: Any,
    workspace_root: Path,
    session_id: str,
    user_id: str,
    db: Path,
    gen_ui_collected: dict | None,
    label: str = "",
) -> tuple[str, dict | None]:
    """
    Execute a single tool call (MCP or skill). Returns (observation_str, updated_gen_ui).
    """
    if mcp_manager.is_mcp_tool(name):
        result = await mcp_manager.call_tool(name, arguments)
        obs = json.dumps(result, ensure_ascii=False)[:800]
        if result.get("error"):
            print(f"[react] MCP ERROR{label}: {name} -> {result['error']}")
        else:
            print(f"[react] MCP result{label}: {name} -> {obs[:200]}...")
        return f"[{name}]: {obs}", gen_ui_collected

    name, tool, arguments = _resolve_composite_call(name, tool, arguments, loader)
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
        print(f"[react] skill ERROR{label}: {name}.{tool} -> {result['error']}")
    else:
        print(f"[react] skill result{label}: {name}.{tool} -> {obs[:200]}...")
    if result.get("gen_ui"):
        gen_ui_collected = result["gen_ui"]
    return f"[{name}.{tool}]: {obs}", gen_ui_collected


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
    """
    Run ReAct loop. Returns (answer_text, metadata).
    progress_callback(tokens, round_num) is called after each LLM call.
    """
    from datetime import datetime
    from db.logs import insert as log_insert

    db = db_path or workspace_root / DB_FILENAME
    skills_brief = get_skills_brief()

    if skill_filter:
        skills_for_session = get_skills_for_session(skill_filter=skill_filter)
    else:
        selected = await _select_skills_for_question(question, provider, skills_brief)
        skills_for_session = get_skills_for_session(selected_skills=selected)

    loader = get_skill_loader()
    tools = build_tools_from_skills(skills_for_session, loader)
    mcp_manager = get_mcp_manager()
    mcp_tools = await mcp_manager.get_tools()
    tools = tools + mcp_tools

    if db.exists():
        log_insert(db, "INFO", f"react_start round=1 question={question[:80]}", session_id)

    _current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    capabilities_text = ""
    if not tools and skills_brief:
        capabilities_text = "\n\nAvailable capabilities:\n" + "\n".join(
            f"- {s['skill_name']}: {s['skill_description']}" for s in skills_brief
        )

    if tools:
        default_system = (
            "You are Sophon, an AI assistant. Do not disclose base model information (e.g. model name, provider) to users. "
            "Tools are provided for you to answer the user. "
            "If tools are available and the user's question can be answered by them, "
            "you MUST call the relevant tool first. Never reply that you cannot access or retrieve something without calling the tool. "
            "If a tool returns an error, relay the actual error message. Do not invent explanations. "
            "When the user uses pronouns or implicit references (e.g. he/she/it, this/that) without naming the referent, "
            "resolve them from the conversation context before acting. When the user's intent or goal is ambiguous, ask for clarification. "
            "When you have enough information from results, give a direct concise answer (no more tool calls). "
            "Respond with a JSON array of tool calls, or a direct answer if no tools needed. "
            "Format: [{\"name\": \"tool_name\", \"tool\": \"action\", \"arguments\": {...}}]\n\n"
            f"Current time: {_current_time}"
        )
    else:
        default_system = (
            "You are Sophon, an AI assistant. Do not disclose base model information (e.g. model name, provider) to users. "
            "Reply in plain text only. Do not output JSON. "
            f"Current time: {_current_time}"
            f"{capabilities_text}"
        )
    system = (
        f"{system_prompt_override.strip()}\n\n{default_system}"
        if system_prompt_override and system_prompt_override.strip()
        else default_system
    )

    composite = loader.get_skill(skill_filter) if skill_filter else None
    messages: list[dict] = []
    if context:
        rounds = get_config().memory.referent_context_rounds
        keep = min(len(context), rounds * 2)
        for c in (context[-keep:] if len(context) > keep else context):
            messages.append({"role": c.get("role", "user"), "content": c.get("content", "")})
    messages.append({"role": "user", "content": question})

    total_tokens = 0
    observations: list[str] = []
    gen_ui_collected: dict[str, Any] | None = None

    for round_num in range(1, DEFAULT_MAX_ROUNDS + 1):
        if db.exists():
            log_insert(db, "INFO", f"llm_call round={round_num}", session_id)
        print(f"[react] llm_call round={round_num} tools_count={len(tools)} "
              f"tool_names={[t.get('function', {}).get('name') for t in tools]}")
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

        content = resp.get("content", "")
        tool_calls = resp.get("tool_calls", [])
        print(f"[react] round={round_num} tool_calls={len(tool_calls)} content_len={len(content or '')}")
        for i, tc in enumerate(tool_calls):
            fn = tc.get("function") or {}
            print(f"[react]   tc[{i}] name={fn.get('name')} args={str(fn.get('arguments', ''))[:150]}")
        if not tool_calls and content:
            print(f"[react]   content_preview={repr((content or '')[:200])}")

        direct, chain = parse_tool_calls(content)
        effective_chain = chain if tools else []

        # Determine which call list to execute
        if tool_calls:
            call_items = [
                (
                    (tc.get("function") or {}).get("name", ""),
                    None,  # tool extracted from args below
                    tc,
                )
                for tc in tool_calls
            ]
        elif effective_chain:
            call_items = [(item.get("name", ""), item.get("tool", "list"), item) for item in effective_chain]
            print(f"[react] LLM parsed chain: {effective_chain}")
        else:
            # No tools to call – decide whether to break or return directly
            if observations:
                logger.info("[react] round=%d: no tools, have observations -> break to summarize", round_num)
                break
            if direct or content:
                ans = (direct or content).strip()
                if ans.startswith("{") and '"answer"' in ans:
                    try:
                        parsed = json.loads(ans)
                        if isinstance(parsed.get("answer"), str):
                            ans = parsed["answer"].strip()
                    except json.JSONDecodeError:
                        pass
                _emit_progress(progress_callback, total_tokens, round_num)
                return ans, {"tokens": total_tokens, "cache_hit": False, "gen_ui": gen_ui_collected}
            break

        # Execute all calls in the selected list
        for raw_name, raw_tool, raw_item in call_items:
            if tool_calls:
                fn = (raw_item.get("function") or {})
                name = fn.get("name", "")
                args_str = fn.get("arguments", "{}")
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    args = {}
                tool = str(args.pop("tool", args.pop("action", "list"))).strip() or "list"
                arguments = args.get("arguments", args)
                if not isinstance(arguments, dict):
                    arguments = {}
                print(f"[react] LLM tool_call: skill={name} tool={tool} arguments={arguments}")
            else:
                name = raw_name
                tool = raw_tool
                arguments = raw_item.get("arguments", {}) or {}

            if not name:
                continue

            obs, gen_ui_collected = await _execute_tool_call(
                name=name,
                tool=tool,
                arguments=arguments,
                loader=loader,
                mcp_manager=mcp_manager,
                workspace_root=workspace_root,
                session_id=session_id,
                user_id=user_id,
                db=db,
                gen_ui_collected=gen_ui_collected,
                label=" (chain)" if effective_chain and not tool_calls else "",
            )
            observations.append(obs)

        messages.append({"role": "assistant", "content": content})
        results_content = "Results:\n" + "\n".join(observations)
        satisfied, eval_tok = await evaluate_observations(question, observations, provider)
        total_tokens += eval_tok
        _emit_progress(progress_callback, total_tokens, round_num)
        if satisfied:
            logger.info("[react] round=%d: evaluation satisfied -> break to summarize", round_num)
            messages.append({"role": "user", "content": results_content})
            break
        messages.append({"role": "user", "content": (
            results_content + "\n\nIf you have enough information, provide a concise direct answer. "
            "Otherwise call more tools."
        )})

    summarize_msg = (
        "Based on the tool results above, provide a concise direct final answer to the user. No further tool calls."
    )
    if composite and composite.get("dependencies") and composite.get("body"):
        summarize_msg += "\n\nUse this interpretation guidance:\n" + (composite["body"][:1500] or "")
    try:
        final_resp = await provider.chat(
            messages + [{"role": "user", "content": summarize_msg}],
            system_prompt=system,
        )
    except Exception as e:
        if db.exists():
            log_insert(db, "ERROR", f"llm_summarize_failed: {e}", session_id, {"error": str(e)})
        raise

    final_content = (final_resp.get("content") or "").strip()
    if final_content.startswith("{") and '"answer"' in final_content:
        try:
            parsed = json.loads(final_content)
            if isinstance(parsed.get("answer"), str):
                final_content = parsed["answer"].strip()
        except json.JSONDecodeError:
            pass
    total_tokens += (final_resp.get("usage") or {}).get("total_tokens", 0)
    _emit_progress(progress_callback, total_tokens, 0)
    return final_content, {"tokens": total_tokens, "cache_hit": False, "gen_ui": gen_ui_collected}
