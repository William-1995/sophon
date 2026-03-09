"""
Base LLM Provider Interface.

Defines the abstract base class that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    """Abstract base class for LLM providers.

    All concrete providers must implement the chat() method to send messages
    to their respective LLM backends and return standardized responses.
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system_prompt: str = "",
    ) -> dict[str, Any]:
        """Send chat request to the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            tools: Optional list of tool definitions for function calling.
            system_prompt: Optional system-level instructions.

        Returns:
            Dict with keys:
                - content: The LLM's text response.
                - tool_calls: List of tool call requests (empty if none).
                - usage: Token usage statistics dict.
        """
        pass
