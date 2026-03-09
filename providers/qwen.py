"""
Qwen/DashScope API Provider.

Implementation for Alibaba's Qwen models via DashScope platform.
Requires DASHSCOPE_API_KEY environment variable.
"""

import os
from typing import Any

from providers.openai_base import OpenAICompatibleProvider

_DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DEFAULT_MODEL = "qwen-plus"


class QwenProvider(OpenAICompatibleProvider):
    """Qwen/DashScope API provider.

    Uses environment variables for configuration:
    - DASHSCOPE_API_KEY: Required API key.
    - QWEN_BASE_URL: Optional custom endpoint (defaults to official API).
    - QWEN_MODEL: Optional model override (defaults to qwen-plus).

    Supported models include qwen-plus, qwen-turbo, qwen-max, etc.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        **kwargs,
    ):
        """Initialize Qwen provider with environment-based defaults.

        Args:
            base_url: Optional custom API endpoint URL.
            model: Optional model identifier override.
            api_key: Optional API key (defaults to DASHSCOPE_API_KEY env var).
            **kwargs: Additional arguments passed to OpenAICompatibleProvider.

        Raises:
            ValueError: If no API key is provided and DASHSCOPE_API_KEY is not set.
        """
        resolved_api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        if not resolved_api_key:
            raise ValueError(
                "DASHSCOPE_API_KEY is required. Set it in environment or pass api_key."
            )

        super().__init__(
            base_url=base_url or os.getenv("QWEN_BASE_URL", _DEFAULT_BASE_URL),
            api_key=resolved_api_key,
            model=model or os.getenv("QWEN_MODEL", _DEFAULT_MODEL),
            **kwargs,
        )
