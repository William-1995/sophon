"""Which skill/action the orchestrator uses to resolve ``@filename`` references."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileInjectionConfig:
    """Maps chat ``@file`` handling to a concrete skill invocation.

    Attributes:
        skill (str): Skill name (default ``filesystem``).
        action (str): Action name passed as tool (default ``read``).
    """

    skill: str = "filesystem"
    action: str = "read"
