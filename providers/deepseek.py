"""
DeepSeek API Provider.

Implementation for DeepSeek's OpenAI-compatible API.
Requires DEEPSEEK_API_KEY environment variable.
"""

import os
from config.defaults import DEFAULT_MODEL
from providers.openai_base import OpenAICompatibleProvider

_DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
_DEFAULT_MODEL = DEFAULT_MODEL


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek API provider.

    Uses environment variables for configuration:
    - DEEPSEEK_API_KEY: Required API key.
    - DEEPSEEK_BASE_URL: Optional custom endpoint (defaults to official API).
    - DEEPSEEK_MODEL: Optional model override (defaults to the configured model).
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        **kwargs,
    ):
        """Initialize DeepSeek provider with environment-based defaults.

        Args:
            base_url: Optional custom API endpoint URL.
            model: Optional model identifier override.
            api_key: Optional API key (defaults to DEEPSEEK_API_KEY env var).
            **kwargs: Additional arguments passed to OpenAICompatibleProvider.

        Raises:
            ValueError: If no API key is provided and DEEPSEEK_API_KEY is not set.
        """
        resolved_api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        if not resolved_api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY is required. Set it in environment or pass api_key."
            )

        super().__init__(
            base_url=base_url or os.getenv("DEEPSEEK_BASE_URL", _DEFAULT_BASE_URL),
            api_key=resolved_api_key,
            model=model or os.getenv("DEEPSEEK_MODEL", _DEFAULT_MODEL),
            **kwargs,
        )
