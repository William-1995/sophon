"""
Skill Executor - Subprocess and IPC helpers.

Runs skill scripts via subprocess, supports event pipe on Unix.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from constants import EXECUTOR_EVENT_DRAIN_TIMEOUT, SKILL_TIMEOUT

logger = logging.getLogger(__name__)


def build_run_env(project_root: Path, env: dict[str, str] | None) -> dict[str, str]:
    """Build environment for skill subprocess.

    Copies os.environ and sets PYTHONPATH, SOPHON_ROOT; merges optional env.
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


def run_script_subprocess_sync(
    script_path: Path,
    params: dict[str, Any],
    timeout: int,
    project_root: Path,
    env: dict[str, str] | None,
) -> tuple[str, str, int]:
    """Run script via subprocess.run. Windows fallback."""
    run_env = build_run_env(project_root, env)
    run_env["PYTHONIOENCODING"] = "utf-8"
    payload = json.dumps(params, ensure_ascii=False).encode("utf-8", errors="replace")
    try:
        result = subprocess.run(
            [sys.executable, str(script_path.resolve())],
            input=payload,
            capture_output=True,
            timeout=timeout,
            env=run_env,
            cwd=str(script_path.parent),
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Skill timed out after {timeout}s")


def ensure_script_success_sync(return_code: int, stdout: bytes, stderr: bytes) -> str:
    """Raise RuntimeError if non-zero; else return decoded stdout."""
    if return_code != 0:
        err = stderr.decode("utf-8", errors="replace") or stdout.decode("utf-8", errors="replace")
        raise RuntimeError(f"Skill failed (exit {return_code}): {err}")
    return stdout.decode("utf-8", errors="replace")


def prepare_run_env_for_script(
    project_root: Path,
    env: dict[str, str] | None,
    event_sink: Callable[[dict[str, Any]], None] | None,
) -> tuple[dict[str, str], int | None, int | None]:
    """Build run env and optionally set up event pipe on Unix."""
    run_env = build_run_env(project_root, env)
    pipe_r, pipe_w = None, None
    if event_sink and os.name != "nt":
        pipe_r, pipe_w = os.pipe()
        run_env["SOPHON_REPORT_EVENTS"] = "1"
        run_env["SOPHON_EVENT_FD"] = str(pipe_w)
        run_env["SOPHON_IPC_FORMAT"] = (
            (os.environ.get("SOPHON_IPC_FORMAT") or "json").strip().lower() or "json"
        )
    return run_env, pipe_r, pipe_w


async def create_skill_process(
    script_path: Path,
    run_env: dict[str, str],
    pipe_w: int | None,
) -> asyncio.subprocess.Process:
    """Create skill subprocess; close write end of event pipe in parent."""
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


def start_event_drain_task(
    pipe_r: int | None,
    run_env: dict[str, str],
    event_sink: Callable[[dict[str, Any]], None] | None,
) -> asyncio.Task | None:
    """Start background task that drains events from pipe into event_sink."""
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


async def write_script_stdin(
    proc: asyncio.subprocess.Process,
    params: dict[str, Any],
) -> None:
    """Send params as JSON on stdin, drain, and close stdin."""
    payload = json.dumps(params, ensure_ascii=False).encode("utf-8", errors="replace")
    proc.stdin.write(payload)
    await proc.stdin.drain()
    proc.stdin.close()


async def drain_event_task(
    event_task: asyncio.Task,
    timeout: float = EXECUTOR_EVENT_DRAIN_TIMEOUT,
) -> None:
    """Wait for event drain task or cancel on timeout."""
    try:
        await asyncio.wait_for(event_task, timeout=timeout)
    except asyncio.TimeoutError:
        event_task.cancel()
        try:
            await event_task
        except asyncio.CancelledError:
            pass


async def wait_and_collect_script_output(
    proc: asyncio.subprocess.Process,
    timeout: int,
    event_task: asyncio.Task | None,
) -> tuple[bytes, bytes]:
    """Wait for process (with timeout), drain event task, return (stdout, stderr)."""
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
            await drain_event_task(event_task)
        raise TimeoutError(f"Skill timed out after {timeout}s")
    stdout = await stdout_task
    stderr = await proc.stderr.read()
    if event_task is not None:
        await drain_event_task(event_task)
    return stdout, stderr


def ensure_script_success(
    proc: asyncio.subprocess.Process,
    stdout: bytes,
    stderr: bytes,
) -> str:
    """Raise RuntimeError if proc.returncode != 0; else return decoded stdout."""
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace") or stdout.decode("utf-8", errors="replace")
        raise RuntimeError(f"Skill failed (exit {proc.returncode}): {err}")
    return stdout.decode("utf-8", errors="replace")


async def run_script(
    script_path: Path,
    params: dict[str, Any],
    timeout: int = SKILL_TIMEOUT,
    env: dict[str, str] | None = None,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
) -> str:
    """Run a skill script via subprocess and return its stdout.

    When event_sink is provided (and on Unix), a pipe is used for real-time
    events. Events (NDJSON or MessagePack) are parsed and passed to event_sink.
    """
    project_root = Path(__file__).resolve().parent.parent
    if sys.platform == "win32":
        stdout_bytes, stderr_bytes, return_code = await asyncio.to_thread(
            run_script_subprocess_sync,
            script_path,
            params,
            timeout,
            project_root,
            env,
        )
        return ensure_script_success_sync(return_code, stdout_bytes, stderr_bytes)

    run_env, pipe_r, pipe_w = prepare_run_env_for_script(project_root, env, event_sink)
    proc = await create_skill_process(script_path, run_env, pipe_w)
    event_task = start_event_drain_task(pipe_r, run_env, event_sink)
    await write_script_stdin(proc, params)
    stdout_bytes, stderr_bytes = await wait_and_collect_script_output(
        proc, timeout, event_task
    )
    return ensure_script_success(proc, stdout_bytes, stderr_bytes)
