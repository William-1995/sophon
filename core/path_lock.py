"""
Path-based lock for tool calls - prevents race when parallel tool executions
target the same paths (e.g. write/delete/rename).

Skills opt-in via adapters that register (skill_name, action) -> path extractor.
Framework is agnostic: only checks the registry.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# Registry: (skill_name, action) -> extractor(args: dict) -> list[str]
_PATH_EXTRACTORS: dict[tuple[str, str], Callable[[dict], list[str]]] = {}


def register_path_extractor(
    skill_name: str,
    action: str,
    extractor: Callable[[dict], list[str]],
) -> None:
    """Register path extractor for (skill_name, action). Adapters call this on import."""
    _PATH_EXTRACTORS[(skill_name, action)] = extractor


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


def _evict_one_unlocked() -> bool:
    """Evict one unlocked lock (FIFO among unlocked). Returns True if evicted."""
    for k in list(_PATH_LOCKS.keys()):
        if not _PATH_LOCKS[k].locked():
            del _PATH_LOCKS[k]
            return True
    return False


def _get_path_lock(workspace_root: Path, path: str) -> asyncio.Lock:
    """Get or create a lock for (workspace, path). Evicts only unlocked locks when at limit."""
    key = _lock_key(workspace_root, path)
    if key not in _PATH_LOCKS:
        if len(_PATH_LOCKS) >= _PATH_LOCK_MAX:
            if not _evict_one_unlocked():
                # All locks held; allow over-limit (better than blocking)
                logger.warning(
                    "[path_lock] cache full (%d), all locks held; creating new lock (over limit)",
                    _PATH_LOCK_MAX,
                )
        _PATH_LOCKS[key] = asyncio.Lock()
    return _PATH_LOCKS[key]


def get_locks_for_tool_call(
    workspace_root: Path,
    skill_name: str,
    action: str,
    arguments: dict,
) -> list[asyncio.Lock]:
    """Return locks to acquire for (skill_name, action). Uses registry; no skill-specific logic."""
    extract = _PATH_EXTRACTORS.get((skill_name, action))
    paths = extract(arguments) if extract else []
    return [_get_path_lock(workspace_root, p) for p in paths]


# Import adapters to populate registry (deferred to avoid circular import)
def _register_builtin_adapters() -> None:
    from core.adapters import filesystem_lock  # noqa: F401


_register_builtin_adapters()
