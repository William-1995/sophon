"""Subprocess execution helpers for skill scripts and IPC event streaming.

This module provides sync/async runners, environment preparation, optional
event-pipe wiring on Unix, timeout handling, and uniform stdout/error decoding.
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
from core.runtime_paths import build_skill_subprocess_pythonpath

logger = logging.getLogger(__name__)


def build_run_env(
    project_root: Path,
    env: dict[str, str] | None,
    *,
    script_path: Path | None = None,
) -> dict[str, str]:
    """Build environment variables for a skill subprocess.

    Starts from ``os.environ``, injects ``PYTHONPATH`` and ``SOPHON_ROOT``, then
    overlays caller-provided env values.

    Args:
        project_root (Path): Sophon project root used for runtime path building.
        env (dict[str, str] | None): Optional overrides/extra variables.
        script_path (Path | None): Script path used to compose PYTHONPATH segments.

    Returns:
        dict[str, str]: Environment mapping for subprocess execution.
    """
    run_env = os.environ.copy()
    run_env["PYTHONPATH"] = build_skill_subprocess_pythonpath(project_root, script_path)
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
    """Run one script with ``subprocess.run`` (sync fallback, mainly Windows).

    Args:
        script_path (Path): Script file to execute.
        params (dict[str, Any]): JSON payload written to stdin.
        timeout (int): Max runtime in seconds.
        project_root (Path): Project root used by env setup.
        env (dict[str, str] | None): Optional environment overrides.

    Returns:
        tuple[str, str, int]: ``(stdout_bytes, stderr_bytes, return_code)``.

    Raises:
        TimeoutError: If execution exceeds ``timeout``.
    """
    run_env = build_run_env(project_root, env, script_path=script_path)
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
    """Validate sync subprocess exit status and decode stdout.

    Args:
        return_code (int): Process return code.
        stdout (bytes): Captured stdout bytes.
        stderr (bytes): Captured stderr bytes.

    Returns:
        str: UTF-8 decoded stdout text.

    Raises:
        RuntimeError: If ``return_code`` is non-zero.
    """
    if return_code != 0:
        err = stderr.decode("utf-8", errors="replace") or stdout.decode("utf-8", errors="replace")
        raise RuntimeError(f"Skill failed (exit {return_code}): {err}")
    return stdout.decode("utf-8", errors="replace")


def prepare_run_env_for_script(
    project_root: Path,
    env: dict[str, str] | None,
    event_sink: Callable[[dict[str, Any]], None] | None,
    *,
    script_path: Path | None = None,
) -> tuple[dict[str, str], int | None, int | None]:
    """Prepare environment and optional Unix event-pipe descriptors.

    Args:
        project_root (Path): Sophon project root.
        env (dict[str, str] | None): Optional environment overrides.
        event_sink (Callable[[dict[str, Any]], None] | None): Event consumer callback.
        script_path (Path | None): Script path used to compose PYTHONPATH.

    Returns:
        tuple[dict[str, str], int | None, int | None]:
            ``(run_env, pipe_r, pipe_w)``. Pipe fds are ``None`` when events are disabled.
    """
    run_env = build_run_env(project_root, env, script_path=script_path)
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
    """Create async subprocess for a skill script.

    Args:
        script_path (Path): Script file to execute.
        run_env (dict[str, str]): Prepared environment mapping.
        pipe_w (int | None): Write fd passed to child for event IPC on Unix.

    Returns:
        asyncio.subprocess.Process: Running process handle.
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


def start_event_drain_task(
    pipe_r: int | None,
    run_env: dict[str, str],
    event_sink: Callable[[dict[str, Any]], None] | None,
) -> asyncio.Task | None:
    """Start background task that forwards child IPC events to ``event_sink``.

    Args:
        pipe_r (int | None): Read fd for event pipe.
        run_env (dict[str, str]): Runtime env (used for IPC format selection).
        event_sink (Callable[[dict[str, Any]], None] | None): Event callback.

    Returns:
        asyncio.Task | None: Drain task, or ``None`` when event piping is disabled.
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


async def write_script_stdin(
    proc: asyncio.subprocess.Process,
    params: dict[str, Any],
) -> None:
    """Write JSON payload to child stdin, flush, and close the stream.

    Args:
        proc (asyncio.subprocess.Process): Running skill process.
        params (dict[str, Any]): Payload serialized to stdin JSON.
    """
    payload = json.dumps(params, ensure_ascii=False).encode("utf-8", errors="replace")
    proc.stdin.write(payload)
    await proc.stdin.drain()
    proc.stdin.close()


async def drain_event_task(
    event_task: asyncio.Task,
    timeout: float = EXECUTOR_EVENT_DRAIN_TIMEOUT,
) -> None:
    """Await event drain completion with timeout and safe cancellation.

    Args:
        event_task (asyncio.Task): Event-drain task handle.
        timeout (float): Max seconds to wait before cancelling.
    """
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
    """Wait for process completion, then collect stdout/stderr and drain events.

    Args:
        proc (asyncio.subprocess.Process): Running process.
        timeout (int): Max runtime in seconds.
        event_task (asyncio.Task | None): Optional event-drain task.

    Returns:
        tuple[bytes, bytes]: ``(stdout, stderr)`` bytes.

    Raises:
        TimeoutError: If the process exceeds ``timeout``.
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
    """Validate async subprocess return code and decode stdout.

    Args:
        proc (asyncio.subprocess.Process): Completed process handle.
        stdout (bytes): Captured stdout bytes.
        stderr (bytes): Captured stderr bytes.

    Returns:
        str: UTF-8 decoded stdout text.

    Raises:
        RuntimeError: If process exit code is non-zero.
    """
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
    """Run a skill script and return decoded stdout.

    Uses sync ``subprocess.run`` path on Windows; uses async subprocess + optional
    event pipe path on Unix when ``event_sink`` is provided.

    Args:
        script_path (Path): Script file to execute.
        params (dict[str, Any]): JSON payload for stdin.
        timeout (int): Max runtime in seconds.
        env (dict[str, str] | None): Optional environment overrides.
        event_sink (Callable[[dict[str, Any]], None] | None): Real-time event callback.

    Returns:
        str: Decoded stdout text.

    Raises:
        TimeoutError: If the script exceeds ``timeout``.
        RuntimeError: If the script exits with non-zero status.
    """
    from core.runtime_paths import sophon_project_root

    project_root = sophon_project_root()
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

    run_env, pipe_r, pipe_w = prepare_run_env_for_script(
        project_root, env, event_sink, script_path=script_path
    )
    proc = await create_skill_process(script_path, run_env, pipe_w)
    event_task = start_event_drain_task(pipe_r, run_env, event_sink)
    await write_script_stdin(proc, params)
    stdout_bytes, stderr_bytes = await wait_and_collect_script_output(
        proc, timeout, event_task
    )
    return ensure_script_success(proc, stdout_bytes, stderr_bytes)
