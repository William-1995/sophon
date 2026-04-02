#!/usr/bin/env python3
"""Launches Sophon for local development with optional setup and the HTTP API.

Adds the repository root to sys.path (bootstrap_paths), then either performs a
full developer setup or only ensures the database exists before starting
uvicorn.

Note:
    PORT sets the API listen port; default is DEFAULT_API_PORT in config package.
    LOG_LEVEL sets root logging (default INFO); httpx, httpcore, and
    uvicorn.access are capped at WARNING.

Example:
    python start.py
    python start.py api-only
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import bootstrap_paths
from config import get_config

_ROOT = bootstrap_paths.activate()

def _run(cmd: list[str], label: str) -> bool:
    """Runs a subprocess with the repository root as working directory.

    Args:
        cmd (list[str]): Argument list for subprocess.run; first element is the
            executable.
        label (str): Message printed to stdout before the command runs.

    Returns:
        True if the child process exited with code 0. If the code is non-zero
        and stderr is non-empty, stderr is copied to this process's stderr.
    """
    print(label)
    r = subprocess.run(cmd, cwd=_ROOT, capture_output=True, text=True)
    if r.returncode != 0 and r.stderr:
        print(r.stderr, file=sys.stderr)
    return r.returncode == 0


def _db_init() -> bool:
    """Creates or migrates the SQLite database using a child Python process.

    Runs inline code in a subprocess so db.schema and config resolve paths the
    same way as the main application.

    Returns:
        True if ensure_db_ready completed successfully; False if the subprocess
        failed (details written to stderr).
    """
    print("Initializing database")
    script = """
from db.schema import ensure_db_ready, configure_default_database
from config import get_config

db_path = get_config().paths.db_path()
configure_default_database(db_path)
ensure_db_ready(db_path)
print("Database ready")
"""
    r = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_ROOT,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(f"Database init failed: {r.stderr or r.stdout}", file=sys.stderr)
        return False
    if r.stdout:
        print(r.stdout.rstrip())
    return True


def _install_deps() -> bool:
    """Installs packages from requirements.txt when that file exists.

    Returns:
        True if there is no requirements file or pip install exited successfully.
    """
    req = _ROOT / "requirements.txt"
    if req.exists():
        return _run(
            [sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
            "Installing Python dependencies",
        )
    return True


def _install_playwright() -> bool:
    """Installs Playwright's Chromium browser for crawler-related skills.

    Returns:
        True if playwright install chromium exited successfully.
    """
    return _run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        "Installing Playwright Chromium",
    )


def _configure_logging() -> None:
    """Configures stdlib logging before uvicorn starts.

    Uses environment variable LOG_LEVEL (default INFO). Sets httpx, httpcore,
    and uvicorn.access loggers to WARNING.
    """
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    for name in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _run_backend() -> None:
    """Starts the FastAPI application with uvicorn and reload enabled.

    Binds to 0.0.0.0 on get_config().server.api_port. On KeyboardInterrupt,
    prints a short message and returns.
    """
    port = get_config().server.api_port
    print(f"API: http://localhost:{port}")
    print(f"API docs: http://localhost:{port}/docs")
    print("Stop with Ctrl+C\n")
    _configure_logging()
    import uvicorn

    try:
        uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
    except KeyboardInterrupt:
        print("Server stopped")


def main() -> None:
    """Parses the launcher mode and runs install, database, and server steps.

    Raises:
        SystemExit: With code 1 if database initialization fails.

    Note:
        In dev mode, pip or Playwright failures only emit warnings to stderr;
        execution continues unless DB init fails.
    """
    parser = argparse.ArgumentParser(
        description="Sophon launcher",
        epilog="See module docstring for PORT, LOG_LEVEL, and examples.",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="dev",
        choices=("dev", "api-only"),
        help="dev: install + DB + API; api-only: DB + API only",
    )
    args = parser.parse_args()

    if args.mode == "api-only":
        if not _db_init():
            sys.exit(1)
        _run_backend()
        return

    if not _install_deps():
        print("Warning: dependency install reported errors; continuing.", file=sys.stderr)
    if not _install_playwright():
        print("Warning: Playwright install reported errors; continuing.", file=sys.stderr)
    if not _db_init():
        sys.exit(1)
    _run_backend()


if __name__ == "__main__":
    main()
