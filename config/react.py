"""ReAct loop limits, parallelism, HITL, thinking blocks, and legacy todos flag."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .common import safe_env_float


@dataclass(frozen=True)
class ReactConfig:
    """Tuning for ``core.react`` (rounds, tools, optional HITL tool injection).

    Attributes:
        max_rounds (int): Upper bound on LLM rounds per run.
        max_tokens_per_response (int): Soft cap hint for provider max output tokens.
        max_parallel_tool_calls (int): Concurrent skill invocations per round.
        hitl_enabled (bool): When True, exposes ``request_human_decision`` to the model.
            Env: ``SOPHON_HITL_ENABLED``. Default False; delete confirm uses skill flow.
        hitl_timeout_seconds (float): Wait limit for HITL. Env: ``SOPHON_HITL_TIMEOUT``.
        thinking_enabled (bool): Prompt/surface ``<thinking>`` blocks. Env:
            ``SOPHON_THINKING_ENABLED``.
        todos_enabled (bool): Legacy auto plan-first flag. Env: ``SOPHON_TODOS_ENABLED``.
    """

    max_rounds: int = 5
    max_tokens_per_response: int = 4096
    max_parallel_tool_calls: int = 10
    hitl_enabled: bool = field(
        default_factory=lambda: os.environ.get("SOPHON_HITL_ENABLED", "false").lower()
        in ("1", "true", "yes"),
    )
    hitl_timeout_seconds: float = field(
        default_factory=lambda: safe_env_float("SOPHON_HITL_TIMEOUT", "300"),
    )
    thinking_enabled: bool = field(
        default_factory=lambda: os.environ.get("SOPHON_THINKING_ENABLED", "true").lower()
        in ("1", "true", "yes"),
    )
    todos_enabled: bool = field(
        default_factory=lambda: os.environ.get("SOPHON_TODOS_ENABLED", "false").lower()
        in ("1", "true", "yes"),
    )
