"""
Skill Executor - Run skill scripts or invoke Python tools.

Output contract: skills produce typed output; executor validates against
schema when present. Optional event_sink for real-time subprocess events
(pipe + JSON or MessagePack).
"""

import asyncio
import json
import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from constants import (
    EXECUTOR_EVENT_DRAIN_TIMEOUT,
    EXECUTOR_RESULT_PREVIEW_LEN,
    EXECUTOR_TRACE_PREVIEW_LEN,
    SKILL_TIMEOUT,
)
from config import get_config, get_executor_param_injections
from core.skill_loader import get_skill_loader

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API (call order: entry point first, then helpers used by flow)
# ---------------------------------------------------------------------------


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
    SQLite when db_path is provided. call_stack is used for cycle detection;
    the same skill with a different action is allowed (e.g. excel-ops.run ->
    excel-ops.enrich).

    Args:
        skill_name: Name of the skill to run.
        action: Action name (e.g. run, list).
        arguments: JSON-serializable arguments for the skill script.
        workspace_root: Workspace root path.
        session_id: Session identifier for logging/traces.
        user_id: User identifier.
        root: Optional project root; used to resolve skill loader.
        db_path: Optional SQLite DB path for traces and logs.
        call_stack: Stack of (skill, action) for cycle detection.
        event_sink: Optional callback for real-time subprocess events.
        run_id: Optional run ID passed to script via env.
        agent_id: Optional agent ID passed to script via env.

    Returns:
        Result dict from the skill script. On error, includes an "error" key
        with a message; otherwise contains skill-defined keys (e.g. gen_ui).
    """
    raw_stack = call_stack or []
    err = _check_cycle(skill_name, action, raw_stack)
    if err is not None:
        return err

    err, skill = _load_skill(root, skill_name)
    if err is not None:
        return err

    skill_dir = Path(skill["dir"])
    script_path, resolved_action, available = _resolve_script_path(skill_dir, skill, action)
    if not script_path or not script_path.exists():
        return _error_action_not_found(skill_name, action, available)

    params = _build_skill_params(
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

    timeout = _resolve_timeout(skill_name)
    script_env = _build_script_env(db_path, run_id, agent_id)
    _log_skill_start(skill_name, resolved_action, timeout)
    start = time.time()
    ctx = _SkillRunContext(
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
        return _process_skill_output(ctx, raw_output, script_path, start)
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
        _log_skill_error(db_path, session_id, skill_name, resolved_action, err_msg)
        return {"error": err_msg}


async def run_script(
    script_path: Path,
    params: dict[str, Any],
    timeout: int = SKILL_TIMEOUT,
    env: dict[str, str] | None = None,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
) -> str:
    """Run a skill script via subprocess and return its stdout.

    When event_sink is provided (and on Unix), a pipe is used for real-time
    events: the child gets SOPHON_REPORT_EVENTS=1, SOPHON_EVENT_FD=<fd>, and
    SOPHON_IPC_FORMAT=json|msgpack. Events (NDJSON or length-prefixed
    MessagePack) are parsed and passed to event_sink. JSON is the default;
    set env SOPHON_IPC_FORMAT=msgpack for MessagePack.

    Args:
        script_path: Path to the Python script to execute.
        params: JSON-serializable dict sent to the script on stdin.
        timeout: Subprocess timeout in seconds.
        env: Optional extra env vars (merged with executor run env).
        event_sink: Optional callback for real-time events (Unix only).

    Returns:
        Decoded stdout from the script.

    Raises:
        TimeoutError: If the script does not finish within timeout.
        RuntimeError: If the script exits with non-zero return code.
    """
    project_root = Path(__file__).resolve().parent.parent
    run_env, pipe_r, pipe_w = _prepare_run_env_for_script(project_root, env, event_sink)
    proc = await _create_skill_process(script_path, run_env, pipe_w)
    event_task = _start_event_drain_task(pipe_r, run_env, event_sink)
    await _write_script_stdin(proc, params)
    stdout_bytes, stderr_bytes = await _wait_and_collect_script_output(
        proc, timeout, event_task
    )
    return _ensure_script_success(proc, stdout_bytes, stderr_bytes)


# ---------------------------------------------------------------------------
# Private helpers (call order: as used from public API and each other)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _SkillRunContext:
    """Context for process step: logging and output validation.

    Attributes:
        skill_dir: Skill directory path.
        resolved_action: Resolved action name.
        skill_name: Skill name.
        db_path: Optional SQLite DB path for traces/logs.
        session_id: Session ID.
    """

    skill_dir: Path
    resolved_action: str
    skill_name: str
    db_path: Path | None
    session_id: str


def _normalize_call_stack(raw_stack: list) -> list[tuple[str, str]]:
    """Normalize call stack to list of (skill, action) pairs.

    Args:
        raw_stack: Raw stack (each entry list/tuple of 2+ elements or other).

    Returns:
        List of (skill_name, action) tuples; invalid entries become (str(x), "?").
    """
    return [
        (x[0], x[1]) if isinstance(x, (list, tuple)) and len(x) >= 2 else (str(x), "?")
        for x in raw_stack or []
    ]


def _check_cycle(
    skill_name: str,
    action: str,
    call_stack: list,
) -> dict[str, Any] | None:
    """Return an error dict if (skill_name, action) is already in the call stack.

    Args:
        skill_name: Name of the skill.
        action: Action name.
        call_stack: Raw call stack of (skill, action) entries.

    Returns:
        Error dict with "error" key if cycle detected; None otherwise.
    """
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
    """Load skill by name from the skill loader.

    Args:
        root: Optional project root for the loader.
        skill_name: Name of the skill to load.

    Returns:
        (error_dict, skill_dict). On success error_dict is None; on failure
        skill_dict is None.
    """
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
    """Build error dict for action-not-found and log a warning.

    Args:
        skill_name: Name of the skill.
        action: Requested action that was not found.
        available: List of available action names.

    Returns:
        Dict with "error" key containing a user-facing message.
    """
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
    """Inject MCP bridge URL into params when skill declares MCP and bridge is available.

    Mutates params. Logs a warning if skill declares MCP but bridge URL is not set.

    Args:
        skill: Skill manifest dict (may have "mcp" key).
        params: Params dict to mutate (adds _mcp_bridge_url).
        skill_name: Skill name for logging.
    """
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
    """Build env dict for skill subprocess.

    Args:
        db_path: Optional DB path (sets SOPHON_DB_PATH).
        run_id: Optional run ID (sets SOPHON_RUN_ID).
        agent_id: Optional agent ID (sets SOPHON_AGENT_ID).

    Returns:
        Env dict with set keys, or None if none of the optional args are set.
    """
    env: dict[str, str] | None = {"SOPHON_DB_PATH": str(db_path)} if db_path else None
    if run_id:
        env = env or {}
        env["SOPHON_RUN_ID"] = run_id
    if agent_id:
        env = env or {}
        env["SOPHON_AGENT_ID"] = agent_id
    return env


def _log_skill_start(skill_name: str, resolved_action: str, timeout: int) -> None:
    """Log and stderr-print skill start with timeout.

    Args:
        skill_name: Name of the skill.
        resolved_action: Resolved action name.
        timeout: Timeout in seconds.
    """
    logger.info(
        "[executor] skill=%s action=%s start timeout=%ds",
        skill_name, resolved_action, timeout,
    )
    print(
        f"[executor] skill={skill_name} action={resolved_action} start timeout={timeout}s",
        file=sys.stderr,
        flush=True,
    )


def _process_skill_output(
    ctx: _SkillRunContext,
    raw_output: str,
    script_path: Path,
    start: float,
) -> dict[str, Any]:
    """Parse script output, validate contract, log success; return result or error dict.

    Handles empty output, invalid JSON, and schema validation. On success
    computes latency, logs to DB, and returns the result dict.

    Args:
        ctx: Skill run context (skill_dir, resolved_action, skill_name, db_path, session_id).
        raw_output: Raw stdout string from the skill script.
        script_path: Path to the script (for log messages).
        start: Monotonic start time from before run_script.

    Returns:
        Result dict from the skill (or {"error": "..."} on parse/validation failure).
    """
    out_stripped = (raw_output or "").strip()
    if not out_stripped:
        err_msg = "Skill script returned empty output"
        logger.warning(
            "[executor] skill=%s action=%s empty_output script=%s",
            ctx.skill_name, ctx.resolved_action, script_path,
        )
        _log_skill_error(
            ctx.db_path, ctx.session_id, ctx.skill_name, ctx.resolved_action, err_msg
        )
        return {"error": err_msg}

    try:
        result = json.loads(out_stripped)
    except json.JSONDecodeError as e:
        err_msg = f"Invalid skill output: {e}"
        logger.warning(
            "[executor] skill=%s action=%s json_error script=%s preview=%r",
            ctx.skill_name, ctx.resolved_action, script_path,
            out_stripped[:EXECUTOR_RESULT_PREVIEW_LEN],
        )
        _log_skill_error(
            ctx.db_path, ctx.session_id, ctx.skill_name, ctx.resolved_action, err_msg
        )
        return {"error": err_msg}

    if not _validate_output_contract(ctx.skill_dir, ctx.resolved_action, result):
        result = {k: v for k, v in result.items() if k != "gen_ui"}

    latency_ms = int((time.time() - start) * 1000)
    logger.info(
        "[executor] skill=%s action=%s ok latency_ms=%d",
        ctx.skill_name, ctx.resolved_action, latency_ms,
    )
    print(
        f"[executor] skill={ctx.skill_name} action={ctx.resolved_action} ok latency_ms={latency_ms}",
        file=sys.stderr,
        flush=True,
    )
    _log_skill_success(
        ctx.db_path, ctx.session_id, ctx.skill_name, ctx.resolved_action, result, latency_ms
    )
    return result


def _resolve_script_path(
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
            logger.info(
                "[executor] action_fallback skill=%s requested=%s -> using single action=%s",
                skill_dir.name, requested, resolved_action,
            )
            script_path = None
            for s in skill.get("scripts", []):
                if s.endswith(f"{resolved_action}.py"):
                    script_path = skill_dir / s
                    break
    return script_path, resolved_action, available


def _build_skill_params(
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
    params.update(get_executor_param_injections(skill_name, action))
    return params


def _resolve_timeout(skill_name: str) -> int:
    """Resolve skill timeout from config overrides or default.

    Args:
        skill_name: Name of the skill.

    Returns:
        Timeout in seconds.
    """
    cfg = get_config()
    override = dict(cfg.executor.timeout_overrides).get(skill_name)
    return override if override is not None else cfg.executor.default_timeout


def _validate_output_contract(skill_dir: Path, action: str, result: dict[str, Any]) -> bool:
    """Validate result against output schema if present.

    Args:
        skill_dir: Skill directory (schemas live under schemas/).
        action: Action name (schema file is {action}_output.json).
        result: Parsed result dict to validate.

    Returns:
        True if valid or no schema file exists; False on validation failure
        (caller may strip gen_ui etc.).
    """
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


def _log_skill_error(
    db_path: Path | None,
    session_id: str,
    skill_name: str,
    action: str,
    err_msg: str,
) -> None:
    """Log skill error to DB when db_path is provided and exists.

    Args:
        db_path: Optional SQLite DB path.
        session_id: Session ID.
        skill_name: Skill name.
        action: Action name.
        err_msg: Error message to log.
    """
    if db_path and db_path.exists():
        from db.logs import insert as log_insert
        log_insert(
            db_path,
            "ERROR",
            f"skill_error {skill_name}.{action}: {err_msg}",
            session_id,
            {"error": err_msg},
        )


def _log_skill_success(
    db_path: Path | None,
    session_id: str,
    skill_name: str,
    action: str,
    result: dict,
    latency_ms: int,
) -> None:
    """Write trace and metrics to DB when db_path is provided and exists.

    Args:
        db_path: Optional SQLite DB path.
        session_id: Session ID.
        skill_name: Skill name.
        action: Action name.
        result: Result dict (preview stored in trace).
        latency_ms: Elapsed time in milliseconds.
    """
    if not db_path or not db_path.exists():
        return
    from db.traces import insert as trace_insert
    from db.logs import insert as log_insert
    from db.metrics import insert as metrics_insert
    preview = json.dumps(result, ensure_ascii=False)[:EXECUTOR_TRACE_PREVIEW_LEN]
    trace_insert(db_path, session_id, skill_name, action, 0, preview, {"latency_ms": latency_ms})
    metrics_insert(
        db_path,
        "skill_latency_ms",
        float(latency_ms),
        tags={"skill": skill_name, "action": action, "session_id": session_id},
    )
    if result.get("error"):
        log_insert(
            db_path,
            "ERROR",
            f"skill_error {skill_name}.{action}: {result.get('error', '')}",
            session_id,
            {"error": str(result.get("error"))},
        )
    else:
        log_insert(
            db_path,
            "INFO",
            f"skill_execute {skill_name}.{action}",
            session_id,
            {"latency_ms": latency_ms},
        )


def _build_run_env(project_root: Path, env: dict[str, str] | None) -> dict[str, str]:
    """Build environment for skill subprocess.

    Copies os.environ and sets PYTHONPATH, SOPHON_ROOT; merges optional env.

    Args:
        project_root: Project root path.
        env: Optional extra env vars to merge.

    Returns:
        Full env dict for the subprocess.
    """
    run_env = os.environ.copy()
    primitives_root = project_root / "skills" / "primitives"
    run_env["PYTHONPATH"] = (
        str(project_root)
        + os.pathsep
        + str(primitives_root)
        + os.pathsep
        + run_env.get("PYTHONPATH", "")
    )
    run_env["SOPHON_ROOT"] = str(project_root)
    if env:
        run_env.update(env)
    return run_env


async def _drain_event_task(
    event_task: asyncio.Task,
    timeout: float = EXECUTOR_EVENT_DRAIN_TIMEOUT,
) -> None:
    """Wait for event drain task or cancel on timeout.

    Args:
        event_task: Task that drains the event pipe.
        timeout: Max seconds to wait before cancelling.
    """
    try:
        await asyncio.wait_for(event_task, timeout=timeout)
    except asyncio.TimeoutError:
        event_task.cancel()
        try:
            await event_task
        except asyncio.CancelledError:
            pass


def _prepare_run_env_for_script(
    project_root: Path,
    env: dict[str, str] | None,
    event_sink: Callable[[dict[str, Any]], None] | None,
) -> tuple[dict[str, str], int | None, int | None]:
    """Build run env and optionally set up event pipe.

    On Unix with event_sink, creates a pipe and sets SOPHON_REPORT_EVENTS,
    SOPHON_EVENT_FD, SOPHON_IPC_FORMAT in run_env.

    Args:
        project_root: Project root for _build_run_env.
        env: Optional env overrides.
        event_sink: If set (and not Windows), event pipe is created.

    Returns:
        (run_env, pipe_r, pipe_w). pipe_r/pipe_w are None when no pipe.
    """
    run_env = _build_run_env(project_root, env)
    pipe_r, pipe_w = None, None
    if event_sink and os.name != "nt":
        pipe_r, pipe_w = os.pipe()
        run_env["SOPHON_REPORT_EVENTS"] = "1"
        run_env["SOPHON_EVENT_FD"] = str(pipe_w)
        run_env["SOPHON_IPC_FORMAT"] = (
            (os.environ.get("SOPHON_IPC_FORMAT") or "json").strip().lower() or "json"
        )
    return run_env, pipe_r, pipe_w


async def _create_skill_process(
    script_path: Path,
    run_env: dict[str, str],
    pipe_w: int | None,
) -> asyncio.subprocess.Process:
    """Create skill subprocess; close write end of event pipe in parent.

    Args:
        script_path: Path to the Python script.
        run_env: Environment for the subprocess.
        pipe_w: Write end of event pipe (closed in parent after spawn).

    Returns:
        Subprocess instance with stdin/stdout/stderr piped.
    """
    kwargs: dict[str, Any] = {
        "stdin": asyncio.subprocess.PIPE,
        "stdout": asyncio.subprocess.PIPE,
        "stderr": asyncio.subprocess.PIPE,
        "env": run_env,
        "cwd": str(script_path.parent),
    }
    if pipe_w is not None:
        kwargs["pass_fds"] = (pipe_w,)
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(script_path),
        **kwargs,
    )
    if pipe_w is not None:
        os.close(pipe_w)
    return proc


def _start_event_drain_task(
    pipe_r: int | None,
    run_env: dict[str, str],
    event_sink: Callable[[dict[str, Any]], None] | None,
) -> asyncio.Task | None:
    """Start background task that drains events from pipe into event_sink.

    Args:
        pipe_r: Read end of event pipe.
        run_env: Env dict (SOPHON_IPC_FORMAT for channel).
        event_sink: Callback for each event.

    Returns:
        Asyncio task, or None if pipe_r or event_sink is None.
    """
    if not event_sink or pipe_r is None:
        return None
    from core.ipc import PipeEventChannel
    channel = PipeEventChannel(
        pipe_r,
        format_name=run_env.get("SOPHON_IPC_FORMAT", "json"),
    )
    channel.start()

    async def drain_events() -> None:
        async for evt in channel.read_events():
            try:
                event_sink(evt)
            except Exception as e:
                logger.debug("[executor] event_sink error: %s", e)

    return asyncio.create_task(drain_events())


async def _write_script_stdin(proc: asyncio.subprocess.Process, params: dict[str, Any]) -> None:
    """Send params as JSON on stdin, drain, and close stdin.

    Args:
        proc: Subprocess with stdin pipe.
        params: JSON-serializable dict to send.
    """
    payload = json.dumps(params, ensure_ascii=False).encode("utf-8")
    proc.stdin.write(payload)
    await proc.stdin.drain()
    proc.stdin.close()


async def _wait_and_collect_script_output(
    proc: asyncio.subprocess.Process,
    timeout: int,
    event_task: asyncio.Task | None,
) -> tuple[bytes, bytes]:
    """Wait for process (with timeout), drain event task, return (stdout, stderr).

    Args:
        proc: Subprocess to wait for.
        timeout: Max seconds to wait.
        event_task: Optional event drain task to await after process exits.

    Returns:
        (stdout_bytes, stderr_bytes).

    Raises:
        TimeoutError: If process does not exit within timeout.
    """
    stdout_task = asyncio.create_task(proc.stdout.read())
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        stdout_task.cancel()
        try:
            await stdout_task
        except asyncio.CancelledError:
            pass
        if event_task is not None:
            await _drain_event_task(event_task)
        raise TimeoutError(f"Skill timed out after {timeout}s")
    stdout = await stdout_task
    stderr = await proc.stderr.read()
    if event_task is not None:
        await _drain_event_task(event_task)
    return stdout, stderr


def _ensure_script_success(
    proc: asyncio.subprocess.Process,
    stdout: bytes,
    stderr: bytes,
) -> str:
    """Raise RuntimeError if process failed; else return decoded stdout.

    Args:
        proc: Subprocess (returncode checked).
        stdout: Raw stdout bytes.
        stderr: Raw stderr bytes.

    Returns:
        Decoded stdout string (utf-8, errors=replace).

    Raises:
        RuntimeError: If proc.returncode != 0.
    """
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace") or stdout.decode("utf-8", errors="replace")
        raise RuntimeError(f"Skill failed (exit {proc.returncode}): {err}")
    return stdout.decode("utf-8", errors="replace")
