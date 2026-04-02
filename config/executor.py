"""Skill subprocess timeouts (defaults and optional per-skill overrides)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .defaults import SKILL_TIMEOUT, SKILL_TIMEOUT_OVERRIDES


@dataclass(frozen=True)
class ExecutorConfig:
    """Timeout policy for running skill scripts as subprocesses.

    Attributes:
        default_timeout (int): Seconds before kill when no per-skill override matches.
            Default from ``config.defaults.SKILL_TIMEOUT``.
        timeout_overrides (tuple[tuple[str, int], ...]): Copied from
            ``config.defaults.SKILL_TIMEOUT_OVERRIDES`` at construction time.
    """

    default_timeout: int = SKILL_TIMEOUT
    timeout_overrides: tuple[tuple[str, int], ...] = field(
        default_factory=lambda: tuple(SKILL_TIMEOUT_OVERRIDES.items()),
    )
