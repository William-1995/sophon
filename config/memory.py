"""Long-term memory, history windows, referent context, and search defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .common import safe_env_int


@dataclass(frozen=True)
class MemoryConfig:
    """Controls memory cache size, chat history depth, and scoped search.

    Attributes:
        cache_max_entries (int): In-process memory cache capacity.
        history_recent_count (int): Recent messages loaded for context.
        recent_files_days (int): Window for recent-files UX (days).
        referent_context_rounds (int): How many recent user/assistant rounds
            participate in referent resolution prompts.
        memory_scope_by_parent (bool): When True, memory skills scope to the
            session tree. Env: ``SOPHON_MEMORY_SCOPE_BY_PARENT``.
        memory_search_default_limit (int): Default top-k for ``memory.search``.
            Env: ``SOPHON_MEMORY_SEARCH_DEFAULT_LIMIT``.
    """

    cache_max_entries: int = 1000
    history_recent_count: int = 10
    recent_files_days: int = 7
    referent_context_rounds: int = 3
    memory_scope_by_parent: bool = field(
        default_factory=lambda: os.environ.get("SOPHON_MEMORY_SCOPE_BY_PARENT", "true").lower()
        in ("1", "true", "yes"),
    )
    memory_search_default_limit: int = field(
        default_factory=lambda: safe_env_int("SOPHON_MEMORY_SEARCH_DEFAULT_LIMIT", "200"),
    )
