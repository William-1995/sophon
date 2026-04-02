"""Shared tool catalog for reusable capabilities."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, List


@dataclass
class Tool:
    """Represents a reusable tool capability."""

    name: str
    description: str
    function: Callable[..., Awaitable[Any]]
    parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    async def execute(self, **kwargs: Any) -> Any:
        """Run the tool with the supplied arguments."""
        return await self.function(**kwargs)


class ToolCatalog:
    """Registry for shared tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(
        self,
        name: str,
        description: str,
        function: Callable[..., Awaitable[Any]],
    ) -> None:
        """Register a new tool implementation."""
        parameters = self._describe_parameters(function)
        self._tools[name] = Tool(
            name=name,
            description=description,
            function=function,
            parameters=parameters,
        )

    def get(self, name: str) -> Tool | None:
        """Retrieve a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        """Return all registered tools."""
        return list(self._tools.values())

    @staticmethod
    def _describe_parameters(function: Callable[..., Awaitable[Any]]) -> Dict[str, Dict[str, Any]]:
        sig = inspect.signature(function)
        parameters: Dict[str, Dict[str, Any]] = {}
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            annotation = (
                param.annotation.__name__
                if hasattr(param.annotation, "__name__")
                else str(param.annotation)
            )
            default = None if param.default == inspect.Parameter.empty else param.default
            parameters[param_name] = {
                "type": annotation if param.annotation != inspect.Parameter.empty else "Any",
                "default": default,
                "required": param.default == inspect.Parameter.empty,
            }
        return parameters


tool_catalog = ToolCatalog()


def tool(name: str, description: str) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Decorator that registers a function as a shared tool."""

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        tool_catalog.register(name, description, func)

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        return wrapper

    return decorator