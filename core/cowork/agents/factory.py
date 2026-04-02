"""Agent factory and registry."""

from __future__ import annotations

from collections.abc import Callable

from core.cowork.agent_base import Agent

_AGENT_REGISTRY: dict[str, type[Agent]] = {}


def register_agent(agent_type: str) -> Callable[[type[Agent]], type[Agent]]:
    def decorator(cls: type[Agent]) -> type[Agent]:
        _AGENT_REGISTRY[agent_type] = cls
        return cls

    return decorator


def get_registered_agent_types() -> list[str]:
    return sorted(_AGENT_REGISTRY)


def create_agent(
    agent_type: str,
    agent_id: str,
    role_description: str | None = None,
    skills: list[str] | None = None,
) -> Agent:
    if agent_type not in _AGENT_REGISTRY:
        raise ValueError(f"Unknown agent type: {agent_type}")
    agent_class = _AGENT_REGISTRY[agent_type]
    resolved_role = role_description if role_description is not None else getattr(agent_class, "DEFAULT_ROLE", "")
    return agent_class(agent_id, resolved_role, list(skills or []))
