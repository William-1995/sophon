"""Compatibility skill registry backed by the shared tool catalog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from core.tools import Tool, tool_catalog


@dataclass
class Skill:
    name: str
    description: str
    function: Callable[..., Awaitable[Any]]
    parameters: dict[str, Any]

    async def execute(self, **kwargs: Any) -> Any:
        return await self.function(**kwargs)


class SkillsRegistry:
    """Thin registry that mirrors the shared tools."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
        self._load_default_skills()

    def _load_default_skills(self) -> None:
        for tool in tool_catalog.list_tools():
            self.register_tool(tool)

    def register_tool(self, tool: Tool) -> None:
        self._skills[tool.name] = Skill(
            name=tool.name,
            description=tool.description,
            function=tool.function,
            parameters=tool.parameters,
        )

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_skills(self) -> list[dict[str, Any]]:
        return [
            {
                "name": skill.name,
                "description": skill.description,
                "parameters": skill.parameters,
            }
            for skill in self._skills.values()
        ]

    def has_skill(self, name: str) -> bool:
        return name in self._skills


registry = SkillsRegistry()

