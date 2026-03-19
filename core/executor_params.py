"""
Skill Executor - Parameter and path resolution helpers.

Resolves script paths, builds skill params, and resolves timeouts.
"""

import logging
from pathlib import Path
from typing import Any

from config import get_config, get_executor_param_injections

_logger = logging.getLogger(__name__)


def resolve_script_path(
    skill_dir: Path,
    skill: dict,
    action: str,
) -> tuple[Path | None, str, list[str]]:
    """Resolve script path and available actions.

    Args:
        skill_dir: Skill directory path.
        skill: Skill manifest dict (scripts, action_aliases).
        action: Requested action name.

    Returns:
        (script_path, resolved_action, available). script_path may be None
        if action was fallback-resolved to the single available script.
    """
    action_aliases = skill.get("action_aliases") or {}
    resolved_action = action_aliases.get(action, action)
    script_name = f"{resolved_action}.py"
    script_path = None
    for s in skill.get("scripts", []):
        if s.endswith(script_name):
            script_path = skill_dir / s
            break
    available = [
        Path(s).stem
        for s in skill.get("scripts", [])
        if not s.startswith("_") and s.endswith(".py")
    ]
    if not script_path or not script_path.exists():
        if len(available) == 1 and resolved_action != available[0]:
            requested = resolved_action
            resolved_action = available[0]
            _logger.info(
                "[executor] action_fallback skill=%s requested=%s -> using single action=%s",
                skill_dir.name, requested, resolved_action,
            )
            script_path = None
            for s in skill.get("scripts", []):
                if s.endswith(f"{resolved_action}.py"):
                    script_path = skill_dir / s
                    break
    return script_path, resolved_action, available


def build_skill_params(
    arguments: dict[str, Any],
    workspace_root: Path,
    session_id: str,
    user_id: str,
    call_stack: list,
    db_path: Path | None,
    skill_name: str,
    action: str,
) -> dict[str, Any]:
    """Build params dict for skill script invocation.

    Merges arguments with workspace_root, user_id, session_id, call_stack,
    db_path, and config-driven executor param injections.

    Args:
        arguments: User-provided arguments.
        workspace_root: Workspace root path.
        session_id: Session ID.
        user_id: User ID.
        call_stack: Call stack including current (skill_name, action).
        db_path: Optional DB path.
        skill_name: Skill name.
        action: Action name.

    Returns:
        Params dict for the skill script stdin.
    """
    params = dict(arguments)
    params["workspace_root"] = str(workspace_root)
    params["user_id"] = user_id
    params["_executor_session_id"] = session_id
    params["_call_stack"] = call_stack + [[skill_name, action]]
    if "session_id" not in arguments:
        params["session_id"] = None
    if db_path:
        params["db_path"] = str(db_path)
    params.update(
        get_executor_param_injections(
            skill_name, action,
            db_path=db_path,
            session_id=session_id,
        )
    )
    return params


def resolve_timeout(skill_name: str) -> int:
    """Resolve skill timeout from config overrides or default.

    Args:
        skill_name: Name of the skill.

    Returns:
        Timeout in seconds.
    """
    cfg = get_config()
    override = dict(cfg.executor.timeout_overrides).get(skill_name)
    return override if override is not None else cfg.executor.default_timeout
