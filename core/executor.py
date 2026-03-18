"""
Skill Executor - Run skill scripts or invoke Python tools.

Output contract: skills produce typed output; executor validates against
schema when present. Optional event_sink for real-time subprocess events
(pipe + JSON or MessagePack).
"""

import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.executor_output import SkillRunContext, log_skill_error, process_skill_output
from core.executor_params import build_skill_params, resolve_script_path, resolve_timeout
from core.executor_subprocess import run_script
from core.skill_loader import get_skill_loader

logger = logging.getLogger(__name__)


# Re-export for backward compatibility
__all__ = ["execute_skill", "run_script"]


def _normalize_call_stack(raw_stack: list) -> list[tuple[str, str]]:
    """Normalize call stack to list of (skill, action) pairs."""
    return [
        (x[0], x[1]) if isinstance(x, (list, tuple)) and len(x) >= 2 else (str(x), "?")
        for x in raw_stack or []
    ]


def _check_cycle(
    skill_name: str,
    action: str,
    call_stack: list,
) -> dict[str, Any] | None:
    """Return an error dict if (skill_name, action) is already in the call stack."""
    stack = _normalize_call_stack(call_stack)
    pair = (skill_name, action)
    if pair in stack:
        cycle_msg = f"Cycle detected: {skill_name}.{action} already in call stack {stack}"
        logger.warning(
            "[executor] cycle_detected skill=%s action=%s stack=%s",
            skill_name, action, stack,
        )
        return {"error": cycle_msg}
    return None


def _load_skill(
    root: Path | None,
    skill_name: str,
) -> tuple[dict[str, Any] | None, dict | None]:
    """Load skill by name from the skill loader."""
    loader = get_skill_loader(root)
    skill = loader.get_skill(skill_name)
    if not skill:
        return ({"error": f"Unknown skill: {skill_name}"}, None)
    return (None, skill)


def _error_action_not_found(
    skill_name: str,
    action: str,
    available: list[str],
) -> dict[str, Any]:
    """Build error dict for action-not-found and log a warning."""
    logger.warning(
        "[executor] action_not_found skill=%s action=%s available=%s",
        skill_name, action, available,
    )
    return {
        "error": (
            f"Action '{action}' does not exist in skill '{skill_name}'. "
            f"Available actions: {available}. "
            f"Please retry with a valid action."
        )
    }


def _inject_mcp_bridge(skill: dict, params: dict[str, Any], skill_name: str) -> None:
    """Inject MCP bridge URL into params when skill declares MCP."""
    mcp_servers = skill.get("mcp") or []
    if not mcp_servers:
        return
    from mcp_integration.bridge_server import get_bridge_base_url
    bridge_url = get_bridge_base_url()
    if bridge_url:
        params["_mcp_bridge_url"] = bridge_url.rstrip("/")
    else:
        logger.warning(
            "skill=%s declares mcp=%s but SOPHON_MCP_BRIDGE_URL not set. "
            "Run MCP bridge separately: python run_mcp_bridge.py",
            skill_name,
            mcp_servers,
        )


def _build_script_env(
    db_path: Path | None,
    run_id: str | None,
    agent_id: str | None,
) -> dict[str, str] | None:
    """Build env dict for skill subprocess."""
    env: dict[str, str] | None = {"SOPHON_DB_PATH": str(db_path)} if db_path else None
    if run_id:
        env = env or {}
        env["SOPHON_RUN_ID"] = run_id
    if agent_id:
        env = env or {}
        env["SOPHON_AGENT_ID"] = agent_id
    return env


def _log_skill_start(skill_name: str, resolved_action: str, timeout: int) -> None:
    """Log skill start with timeout."""
    logger.info(
        "[executor] skill=%s action=%s start timeout=%ds",
        skill_name, resolved_action, timeout,
    )


async def execute_skill(
    skill_name: str,
    action: str,
    arguments: dict[str, Any],
    workspace_root: Path,
    session_id: str = "default",
    user_id: str = "default_user",
    root: Path | None = None,
    db_path: Path | None = None,
    call_stack: list | None = None,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
    run_id: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """Execute a skill action and return a result dict.

    Resolves script path, builds params, runs the script via run_script,
    validates output against schema when present, and writes trace/log to
    SQLite when db_path is provided.
    """
    raw_stack = call_stack or []
    err = _check_cycle(skill_name, action, raw_stack)
    if err is not None:
        return err

    err, skill = _load_skill(root, skill_name)
    if err is not None:
        return err

    skill_dir = Path(skill["dir"])
    script_path, resolved_action, available = resolve_script_path(skill_dir, skill, action)
    if not script_path or not script_path.exists():
        return _error_action_not_found(skill_name, action, available)

    params = build_skill_params(
        arguments,
        workspace_root,
        session_id,
        user_id,
        raw_stack + [[skill_name, resolved_action]],
        db_path,
        skill_name,
        resolved_action,
    )
    _inject_mcp_bridge(skill, params, skill_name)

    timeout = resolve_timeout(skill_name)
    script_env = _build_script_env(db_path, run_id, agent_id)
    _log_skill_start(skill_name, resolved_action, timeout)
    start = time.time()
    ctx = SkillRunContext(
        skill_dir=skill_dir,
        resolved_action=resolved_action,
        skill_name=skill_name,
        db_path=db_path,
        session_id=session_id,
    )

    try:
        raw_output = await run_script(
            script_path,
            params,
            timeout=timeout,
            env=script_env,
            event_sink=event_sink,
        )
        return process_skill_output(ctx, raw_output, script_path, start)
    except (TimeoutError, RuntimeError) as e:
        err_msg = str(e)
        logger.warning(
            "[executor] skill=%s action=%s error=%s",
            skill_name, resolved_action, err_msg,
        )
        print(
            f"[executor] skill={skill_name} action={resolved_action} error={err_msg}",
            file=sys.stderr,
            flush=True,
        )
        log_skill_error(db_path, session_id, skill_name, resolved_action, err_msg)
        return {"error": err_msg}
