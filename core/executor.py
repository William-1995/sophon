"""
Skill Executor - Run skill scripts or invoke Python tools.
Output Contract: skills produce typed output; executor validates against schema when present.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from core.skill_loader import get_skill_loader

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
# Heavy skills (multi-LLM, web fetch) need longer timeouts
_SKILL_TIMEOUTS: dict[str, int] = {
    "deep-research": 300,
    "crawler": 60,
}


def _validate_output_contract(skill_dir: Path, action: str, result: dict[str, Any]) -> bool:
    """Validate result against output schema if present. Returns True if valid or no schema."""
    schema_path = skill_dir / "schemas" / f"{action}_output.json"
    if not schema_path.exists():
        return True
    try:
        import jsonschema
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(instance=result, schema=schema)
        return True
    except Exception as e:
        logger.warning(
            "[executor] output_contract_validation_failed skill=%s action=%s error=%s",
            skill_dir.name,
            action,
            e,
        )
        return False


async def run_script(
    script_path: Path,
    params: dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
    env: dict[str, str] | None = None,
) -> str:
    """Run skill script via subprocess. Returns stdout or raises."""
    import os
    run_env = os.environ.copy()
    project_root = Path(__file__).resolve().parent.parent
    run_env["PYTHONPATH"] = str(project_root) + os.pathsep + run_env.get("PYTHONPATH", "")
    run_env["SOPHON_ROOT"] = str(project_root)
    if env:
        run_env.update(env)
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(script_path),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=run_env,
        cwd=str(script_path.parent),
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=json.dumps(params, ensure_ascii=False).encode("utf-8")),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        proc.kill()
        raise TimeoutError(f"Skill timed out after {timeout}s")
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace") or stdout.decode("utf-8", errors="replace")
        raise RuntimeError(f"Skill failed (exit {proc.returncode}): {err}")
    return stdout.decode("utf-8", errors="replace")


async def execute_skill(
    skill_name: str,
    action: str,
    arguments: dict[str, Any],
    workspace_root: Path,
    session_id: str = "default",
    user_id: str = "default_user",
    root: Path | None = None,
    db_path: Path | None = None,
    call_stack: list[str] | None = None,
) -> dict[str, Any]:
    """
    Execute a skill action. Returns result dict.
    Writes trace and log to SQLite when db_path provided.
    call_stack: stack of skill names for cycle detection (feature skill -> primitive).
    """
    import time
    stack = call_stack or []
    if skill_name in stack:
        cycle_msg = f"Cycle detected: {skill_name} already in call stack {stack}"
        logger.warning("[executor] %s", cycle_msg)
        return {"error": cycle_msg}

    loader = get_skill_loader(root)
    skill = loader.get_skill(skill_name)
    if not skill:
        return {"error": f"Unknown skill: {skill_name}"}
    logger.info("skill=%s action=%s arguments=%s", skill_name, action, arguments)
    skill_dir = Path(skill["dir"])
    scripts_dir = skill_dir / "scripts"
    script_name = f"{action}.py"
    script_path = None
    for s in skill.get("scripts", []):
        if s.endswith(script_name):
            script_path = skill_dir / s
            break
    if not script_path or not script_path.exists():
        available = [
            Path(s).stem
            for s in skill.get("scripts", [])
            if not s.startswith("_") and s.endswith(".py")
        ]
        if len(available) == 1 and action != available[0]:
            requested = action
            action = available[0]
            logger.info(
                "action_fallback skill=%s requested=%s -> using single action=%s",
                skill_name, requested, action,
            )
            script_path = None
            for s in skill.get("scripts", []):
                if s.endswith(f"{action}.py"):
                    script_path = skill_dir / s
                    break
        if not script_path or not script_path.exists():
            logger.warning(
                "action_not_found skill=%s action=%s available=%s",
                skill_name, action, available,
            )
            return {
                "error": (
                    f"Action '{action}' does not exist in skill '{skill_name}'. "
                    f"Available actions: {available}. "
                    f"Please retry with a valid action."
                )
            }
    params = dict(arguments)
    params["workspace_root"] = str(workspace_root)
    params["user_id"] = user_id
    params["_executor_session_id"] = session_id
    params["_call_stack"] = stack + [skill_name]
    if "session_id" not in arguments:
        params["session_id"] = None
    if db_path:
        params["db_path"] = str(db_path)
    if skill_name == "memory" and action == "search":
        from config import get_config
        params["_memory_search_default_limit"] = get_config().memory.memory_search_default_limit
    mcp_servers = skill.get("mcp") or []
    if mcp_servers:
        from mcp_client.bridge_server import get_bridge_base_url
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
    timeout = _SKILL_TIMEOUTS.get(skill_name, DEFAULT_TIMEOUT)
    start = time.time()
    try:
        out = await run_script(script_path, params, timeout=timeout)
        out_stripped = (out or "").strip()
        if not out_stripped:
            err_msg = "Skill script returned empty output"
            logger.warning("[executor] %s.%s: %s script=%s", skill_name, action, err_msg, script_path)
            if db_path and db_path.exists():
                from db.logs import insert as log_insert
                log_insert(db_path, "ERROR", f"skill_error {skill_name}.{action}: {err_msg}", session_id, {"error": err_msg})
            return {"error": err_msg}
        try:
            result = json.loads(out_stripped)
        except json.JSONDecodeError as e:
            err_msg = f"Invalid skill output: {e}"
            logger.warning(
                "[executor] %s.%s: %s script=%s stdout_preview=%r",
                skill_name, action, err_msg, script_path, out_stripped[:200]
            )
            if db_path and db_path.exists():
                from db.logs import insert as log_insert
                log_insert(db_path, "ERROR", f"skill_error {skill_name}.{action}: {err_msg}", session_id, {"error": err_msg})
            return {"error": err_msg}
        if not _validate_output_contract(skill_dir, action, result):
            result = {k: v for k, v in result.items() if k != "gen_ui"}
        latency_ms = int((time.time() - start) * 1000)
        if db_path and db_path.exists():
            from db.traces import insert as trace_insert
            from db.logs import insert as log_insert
            from db.metrics import insert as metrics_insert
            preview = json.dumps(result, ensure_ascii=False)[:500]
            trace_insert(db_path, session_id, skill_name, action, 0, preview, {"latency_ms": latency_ms})
            metrics_insert(
                db_path,
                "skill_latency_ms",
                float(latency_ms),
                tags={"skill": skill_name, "action": action, "session_id": session_id},
            )
            if result.get("error"):
                log_insert(db_path, "ERROR", f"skill_error {skill_name}.{action}: {result.get('error', '')}", session_id, {"error": str(result.get("error"))})
            else:
                log_insert(db_path, "INFO", f"skill_execute {skill_name}.{action}", session_id, {"latency_ms": latency_ms})
        return result
    except (TimeoutError, RuntimeError) as e:
        err_msg = str(e)
        logger.warning("[executor] %s.%s: %s", skill_name, action, err_msg)
        if db_path and db_path.exists():
            from db.logs import insert as log_insert
            log_insert(db_path, "ERROR", f"skill_error {skill_name}.{action}: {err_msg}", session_id, {"error": err_msg})
        return {"error": err_msg}
