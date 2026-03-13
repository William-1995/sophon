"""
OpenAI-compatible API Provider Base.

Provides a reusable implementation for providers that use the OpenAI API format,
including message formatting, surrogate character cleaning, and tool calling.
"""

import logging
from typing import Any

import httpx

from providers.base import BaseProvider

logger = logging.getLogger(__name__)

_TOOL_CHOICE_REQUIRED = "required"


def _clean_surrogates(text: str) -> str:
    """Remove Unicode surrogate characters that can cause JSON encoding errors.

    Surrogates (U+D800-U+DFFF) are invalid in standard UTF-8 and can cause
    issues when serializing LLM responses to JSON.

    Args:
        text: Input text that may contain surrogate characters.

    Returns:
        Text with all surrogate characters removed.
    """
    if not text:
        return text
    return "".join(c for c in text if not (0xD800 <= ord(c) <= 0xDFFF))


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI-compatible API provider implementation.

    Subclasses should set base_url, api_key, and model via the constructor.
    Supports tool calling and automatic surrogate character cleaning.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        timeout: float = 60.0,
    ):
        """Initialize the provider with connection parameters.

        Args:
            base_url: Base URL for the API (e.g., "https://api.example.com/v1").
            api_key: API key for authentication.
            model: Model identifier to use for requests.
            temperature: Sampling temperature (0.0 = deterministic).
            timeout: Request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

    def _build_messages(self, messages: list[dict], system_prompt: str) -> list[dict]:
        """Build the messages list with system prompt and surrogate cleaning.

        Args:
            messages: User/assistant message history.
            system_prompt: System-level instructions to prepend.

        Returns:
            Formatted message list ready for the API request.
        """
        out = []
        if system_prompt:
            out.append({"role": "system", "content": _clean_surrogates(system_prompt)})
        for m in messages:
            out.append({
                "role": m.get("role", "user"),
                "content": _clean_surrogates(m.get("content", "")),
            })
        return out

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system_prompt: str = "",
    ) -> dict[str, Any]:
        """Send chat request to the OpenAI-compatible API.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            tools: Optional list of tool definitions for function calling.
            system_prompt: Optional system-level instructions.

        Returns:
            Dict with content, tool_calls, and usage statistics.

        Raises:
            httpx.HTTPStatusError: If the API returns an error status.
        """
        body: dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "temperature": self.temperature,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = _TOOL_CHOICE_REQUIRED

        url = f"{self.base_url}/chat/completions"

        # Build headers. Some backends (e.g. local Ollama) do not require an API key.
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                url,
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        msg = (data.get("choices") or [{}])[0].get("message") or {}
        result: dict[str, Any] = {
            "content": (msg.get("content") or "").strip(),
            "tool_calls": [],
            "usage": data.get("usage", {}),
        }

        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            result["tool_calls"].append({
                "id": tc.get("id", ""),
                "function": {
                    "name": fn.get("name", ""),
                    "arguments": fn.get("arguments", "{}"),
                },
            })

        if tools and not result["tool_calls"] and result["content"]:
            logger.warning(
                "tools sent but 0 tool_calls returned, msg_keys=%s",
                list(msg.keys()),
            )

        return result
