"""Public config API: ``get_config``, ``bootstrap``, and re-exported dataclasses.

Callers should use ``get_config()`` rather than constructing ``AppConfig`` by hand
so per-user instances are cached. Use ``reset_config_cache_for_tests`` only in tests.
"""

from __future__ import annotations

from .app_config import (
    AppConfig,
    EmotionConfig,
    ExecutorConfig,
    FileInjectionConfig,
    LLMConfig,
    MCPConfig,
    MemoryConfig,
    PathConfig,
    ReactConfig,
    ServerConfig,
    SkillConfig,
    SpeechConfig,
)
from .mcp import MCPServerConfig
from .common import DEFAULT_API_PORT, ROOT, SESSION_ID_LENGTH

_config_cache: dict[str, AppConfig] = {}
_DEFAULT_USER_KEY = "default"


def get_config(user_id: str | None = None) -> AppConfig:
    """Return a cached ``AppConfig`` for the given user id (default user when None).

    Args:
        user_id (str | None): Workspace user key; ``None`` or empty maps to ``default``.

    Returns:
        Shared ``AppConfig`` instance for that key (created on first access).
    """
    key = (user_id or _DEFAULT_USER_KEY).strip() or _DEFAULT_USER_KEY
    if key not in _config_cache:
        _config_cache[key] = AppConfig.from_env(key if key != _DEFAULT_USER_KEY else None)
    return _config_cache[key]


def reset_config_cache_for_tests() -> None:
    """Clear the process-wide config cache (test isolation only)."""
    _config_cache.clear()


def bootstrap(user_id: str | None = None) -> None:
    """Ensure workspace directories exist for the resolved config user.

    Args:
        user_id (str | None): Passed through to ``get_config``.
    """
    cfg = get_config(user_id)
    cfg.paths.ensure_dirs()


__all__ = [
    "AppConfig",
    "DEFAULT_API_PORT",
    "EmotionConfig",
    "ExecutorConfig",
    "FileInjectionConfig",
    "LLMConfig",
    "MCPConfig",
    "MCPServerConfig",
    "MemoryConfig",
    "PathConfig",
    "ReactConfig",
    "ROOT",
    "ServerConfig",
    "SESSION_ID_LENGTH",
    "SkillConfig",
    "SpeechConfig",
    "bootstrap",
    "get_config",
    "reset_config_cache_for_tests",
]
