"""Minimal skill execution bridge used by shared tools.

The current repo exposes search/crawler as shared tools. They expect a
small async adapter that returns structured results. This module keeps that
surface stable without pulling in a larger workflow stack.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from .output import SkillRunContext, process_skill_output
from .params import build_skill_params, resolve_script_path, resolve_timeout
from .subprocess import run_script
from core.skill_loader import get_skill_loader
from config import get_config


async def execute_skill(
    *,
    skill_name: str,
    action: str,
    arguments: dict[str, Any],
    workspace_root: str = "",
    session_id: str = "",
    user_id: str = "default_user",
    db_path: str | None = None,
    event_sink: Any | None = None,
    run_id: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """Execute a supported skill/action pair.

    The implementation is intentionally small: it returns deterministic
    structured payloads for the shared tool wrappers used in tests and
    orchestrator flows.
    """

    _ = (user_id, db_path, event_sink, run_id, agent_id)
    cfg = get_config()
    resolved_workspace_root = Path(workspace_root).resolve() if workspace_root else cfg.paths.user_workspace().resolve()

    skill = get_skill_loader().get_skill(skill_name)
    if skill:
        skill_dir = Path(skill["dir"])
        script_path, resolved_action, available = resolve_script_path(skill_dir, skill, action)
        if script_path is None or not script_path.exists():
            return {
                "success": False,
                "error": f"Unsupported skill/action: {skill_name}.{action}",
                "available_actions": available,
            }

        timeout = resolve_timeout(skill_name)
        params = build_skill_params(
            arguments=arguments,
            workspace_root=resolved_workspace_root,
            session_id=session_id,
            user_id=user_id,
            call_stack=[],
            db_path=Path(db_path) if db_path else None,
            skill_name=skill_name,
            action=resolved_action,
        )
        ctx = SkillRunContext(
            skill_dir=skill_dir,
            resolved_action=resolved_action,
            skill_name=skill_name,
            db_path=Path(db_path) if db_path else None,
            session_id=session_id,
        )
        start = time.time()
        try:
            stdout = await run_script(
                script_path,
                params,
                timeout=timeout,
                event_sink=event_sink,
            )
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "available_actions": available,
            }
        result = process_skill_output(ctx, stdout, script_path, start)
        if result.get("error"):
            return {"success": False, **result, "available_actions": available}
        return result

    return {
        "success": False,
        "error": f"Unsupported skill/action: {skill_name}.{action}",
    }
