"""
LLM Providers - OpenAI-compatible API (DeepSeek, Qwen).
"""

import os
from abc import ABC, abstractmethod
from typing import Any

import httpx

_TOOL_CHOICE_REQUIRED = "required"


class BaseProvider(ABC):
    """Base LLM provider interface."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system_prompt: str = "",
    ) -> dict[str, Any]:
        """Send chat request. Returns content, tool_calls, usage."""
        pass


def _clean_surrogates(text: str) -> str:
    if not text:
        return text
    return "".join(c for c in text if not (0xD800 <= ord(c) <= 0xDFFF))


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI-compatible API base. Subclasses set base_url, api_key, model."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

    def _build_messages(self, messages: list[dict], system_prompt: str) -> list[dict]:
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
        body: dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(messages, system_prompt),
            "temperature": self.temperature,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = _TOOL_CHOICE_REQUIRED
        url = f"{self.base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
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
                "function": {"name": fn.get("name", ""), "arguments": fn.get("arguments", "{}")},
            })
        if tools and not result["tool_calls"] and result["content"]:
            print(f"[provider] tools sent but 0 tool_calls, msg_keys={list(msg.keys())}")
        return result


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek API. Requires DEEPSEEK_API_KEY."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        **kwargs,
    ):
        super().__init__(
            base_url=base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY", ""),
            model=model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            **kwargs,
        )

    async def chat(self, *args, **kwargs) -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is required. Set it in environment.")
        return await super().chat(*args, **kwargs)


class QwenProvider(OpenAICompatibleProvider):
    """Qwen/DashScope API. Requires DASHSCOPE_API_KEY."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        **kwargs,
    ):
        super().__init__(
            base_url=base_url or os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            api_key=api_key or os.getenv("DASHSCOPE_API_KEY", ""),
            model=model or os.getenv("QWEN_MODEL", "qwen-plus"),
            **kwargs,
        )

    async def chat(self, *args, **kwargs) -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY is required. Set it in environment.")
        return await super().chat(*args, **kwargs)


def get_provider(name: str | None = None, model: str | None = None, **kwargs) -> BaseProvider:
    """Get provider by name or by model. Pass name='deepseek'|'qwen' or model='qwen-plus' etc."""
    if name is None:
        name = _model_to_provider(model or "deepseek-chat")
    if name == "deepseek":
        return DeepSeekProvider(model=model or None, **kwargs)
    if name == "qwen":
        return QwenProvider(model=model or None, **kwargs)
    raise ValueError(f"Unknown provider: {name}. Available: deepseek, qwen")


def _model_to_provider(model: str) -> str:
    """Map model name to provider. qwen-* -> qwen, deepseek-* -> deepseek."""
    m = (model or "").lower()
    if m.startswith("qwen"):
        return "qwen"
    return "deepseek"
