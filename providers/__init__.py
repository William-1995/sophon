"""
LLM Providers - Unified interface for multiple LLM backends.

Supports DeepSeek, Qwen (DashScope), and Ollama (local) providers.
All providers implement the OpenAI-compatible chat completions API.

Example:
    from providers import get_provider

    # Get provider by name
    provider = get_provider("deepseek")

    # Or get by model name (auto-detects provider)
    provider = get_provider(model="qwen-plus")

    # Use the provider
    result = await provider.chat(
        messages=[{"role": "user", "content": "Hello"}],
        system_prompt="You are a helpful assistant."
    )
"""

from constants import LLM_TIMEOUT
from providers.base import BaseProvider
from providers.deepseek import DeepSeekProvider
from providers.ollama import OllamaProvider
from providers.qwen import QwenProvider

__all__ = [
    "BaseProvider",
    "DeepSeekProvider",
    "OllamaProvider",
    "QwenProvider",
    "get_provider",
]


def get_provider(name: str | None = None, model: str | None = None, **kwargs) -> BaseProvider:
    """Get a provider instance by name or model identifier.

    Args:
        name: Provider name ('deepseek', 'qwen', 'ollama').
        model: Model identifier (e.g., 'qwen-plus', 'deepseek-chat').
            If name is not provided, the provider is inferred from the model name.
        **kwargs: Additional arguments passed to the provider constructor.

    Returns:
        Configured provider instance ready for chat requests.

    Raises:
        ValueError: If the provider name is unknown or cannot be determined from model.

    Examples:
        >>> provider = get_provider("deepseek")
        >>> provider = get_provider(model="qwen-plus")
        >>> provider = get_provider("ollama", model="llama3.2")
    """
    if name is None:
        name = _model_to_provider(model or "deepseek-chat")

    # Default timeout for all providers, unless explicitly overridden.
    if "timeout" not in kwargs:
        kwargs["timeout"] = float(LLM_TIMEOUT)

    if name == "deepseek":
        return DeepSeekProvider(model=model or None, **kwargs)
    if name == "qwen":
        return QwenProvider(model=model or None, **kwargs)
    if name == "ollama":
        return OllamaProvider(model=model or None, **kwargs)

    raise ValueError(
        f"Unknown provider: {name}. "
        f"Available: deepseek, qwen, ollama"
    )


def _model_to_provider(model: str) -> str:
    """Map model name to provider identifier.

    Args:
        model: Model identifier string.

    Returns:
        Provider name: 'qwen', 'ollama', or 'deepseek' (default).
    """
    m = (model or "").lower()

    # Qwen on Ollama: models like 'qwen3.5:9b' should use OllamaProvider.
    # We treat any 'qwen*' model that includes a colon as an Ollama model.
    if m.startswith("qwen") and ":" in m:
        return "ollama"

    # Cloud Qwen (DashScope), e.g. 'qwen-plus'
    if m.startswith("qwen"):
        return "qwen"

    # Other common Ollama families
    if m.startswith("llama") or m.startswith("mistral") or m.startswith("gemma"):
        return "ollama"

    # Fallback: DeepSeek
    return "deepseek"
