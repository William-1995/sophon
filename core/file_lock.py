"""
File path lock for filesystem skill - prevents race when parallel tool calls
write to the same file.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _noop_context():
    yield


def maybe_acquire_path_locks(locks: list[asyncio.Lock]):
    """Return context manager: acquires locks when non-empty, else no-op."""
    return acquire_path_locks(locks) if locks else _noop_context()


@asynccontextmanager
async def acquire_path_locks(locks: list[asyncio.Lock]):
    """Acquire locks in order, yield, then release. Prevents deadlock."""
    acquired = []
    try:
        for lock in locks:
            await lock.acquire()
            acquired.append(lock)
        yield
    finally:
        for lock in reversed(acquired):
            lock.release()

# Bounded cache: (workspace_root, path) -> Lock. Prune when over limit.
_PATH_LOCKS: dict[str, asyncio.Lock] = {}
_PATH_LOCK_MAX = 64


def _lock_key(workspace_root: Path, path: str) -> str:
    """Normalize path for lock key."""
    p = (path or "").strip().replace("\\", "/")
    root = str(workspace_root.resolve())
    return f"{root}:{p}"


def _get_path_lock(workspace_root: Path, path: str) -> asyncio.Lock:
    """Get or create a lock for (workspace, path). Thread-safe for asyncio."""
    key = _lock_key(workspace_root, path)
    if key not in _PATH_LOCKS:
        if len(_PATH_LOCKS) >= _PATH_LOCK_MAX:
            # Evict oldest (arbitrary); in practice rarely hit
            evict = next(iter(_PATH_LOCKS))
            del _PATH_LOCKS[evict]
        _PATH_LOCKS[key] = asyncio.Lock()
    return _PATH_LOCKS[key]


def _paths_for_write(args: dict) -> list[str]:
    path = args.get("path")
    return [path] if path else []


def _paths_for_delete(args: dict) -> list[str]:
    path = args.get("path")
    files = [f for f in args.get("files") or [] if isinstance(f, str)]
    return sorted(set(filter(None, [path] + files)))[:3]


def _paths_for_rename(args: dict) -> list[str]:
    return sorted(set(filter(None, [args.get("path"), args.get("new_name")])))[:2]


_PATH_EXTRACTORS: dict[str, Callable[[dict], list[str]]] = {
    "write": _paths_for_write,
    "delete": _paths_for_delete,
    "rename": _paths_for_rename,
}


def get_locks_for_filesystem_call(
    workspace_root: Path,
    skill_name: str,
    action: str,
    arguments: dict,
) -> list[asyncio.Lock]:
    """Return locks to acquire for filesystem write/delete/rename. Sorted to avoid deadlock."""
    extract = _PATH_EXTRACTORS.get(action) if skill_name == "filesystem" else None
    paths = extract(arguments) if extract else []
    return [_get_path_lock(workspace_root, p) for p in paths]
