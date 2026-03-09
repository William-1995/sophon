"""
Ollama Local API Provider.

Implementation for locally-hosted models via Ollama.
Uses OpenAI-compatible endpoint provided by Ollama.
"""

import os
from typing import Any

from providers.openai_base import OpenAICompatibleProvider

_DEFAULT_BASE_URL = "http://localhost:11434/v1"
_DEFAULT_MODEL = "qwen3.5:9b"


class OllamaProvider(OpenAICompatibleProvider):
    """Ollama local API provider.

    Connects to a locally running Ollama instance for on-premise LLM inference.

    Uses environment variables for configuration:
    - OLLAMA_BASE_URL: Optional custom endpoint (defaults to localhost:11434).
    - OLLAMA_MODEL: Optional model override (defaults to llama3.2).

    Note: Unlike cloud providers, Ollama typically does not require an API key
    for local access. If authentication is needed, set OLLAMA_API_KEY.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        **kwargs,
    ):
        """Initialize Ollama provider with environment-based defaults.

        Args:
            base_url: Optional custom API endpoint URL.
            model: Optional model identifier override.
            api_key: Optional API key (rarely needed for local instances).
            **kwargs: Additional arguments passed to OpenAICompatibleProvider.
        """
        super().__init__(
            base_url=base_url or os.getenv("OLLAMA_BASE_URL", _DEFAULT_BASE_URL),
            api_key=api_key or os.getenv("OLLAMA_API_KEY", ""),
            model=model or os.getenv("OLLAMA_MODEL", _DEFAULT_MODEL),
            **kwargs,
        )
