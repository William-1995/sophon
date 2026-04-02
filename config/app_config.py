"""Composition root: ``AppConfig`` aggregates all feature-specific config dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field

from .common import DEFAULT_API_PORT, safe_env_int
from .emotion import EmotionConfig
from .executor import ExecutorConfig
from .file_injection import FileInjectionConfig
from .llm import LLMConfig
from .mcp import MCPConfig, resolve_mcp_config
from .memory import MemoryConfig
from .paths import PathConfig
from .react import ReactConfig
from .skills import SkillConfig
from .speech import SpeechConfig


@dataclass(frozen=True)
class ServerConfig:
    """HTTP API server binding for the main FastAPI app (uvicorn).

    Attributes:
        api_port (int): Listen port. Environment: ``PORT``. Default:
            ``DEFAULT_API_PORT`` in ``config.common``.
    """

    api_port: int = field(
        default_factory=lambda: safe_env_int("PORT", str(DEFAULT_API_PORT)),
    )


@dataclass(frozen=True)
class AppConfig:
    """Frozen snapshot of all tunable sections for one logical user/workspace.

    Attributes:
        server (ServerConfig): API port and related server fields.
        paths (PathConfig): Workspace and SQLite paths.
        file_injection (FileInjectionConfig): Skill/action used for ``@file`` reads.
        emotion (EmotionConfig): Emotion sub-agent toggles and weights.
        speech (SpeechConfig): Local STT (faster-whisper) options.
        react (ReactConfig): ReAct loop limits and HITL-related flags.
        executor (ExecutorConfig): Skill subprocess timeouts (defaults from ``constants``).
        memory (MemoryConfig): History, cache, and memory-search defaults.
        skills (SkillConfig): Which skills are exposed to the agent/UI.
        llm (LLMConfig): Default chat model id.
        mcp (MCPConfig): Optional MCP server definitions and bridge URL placeholder.
    """

    server: ServerConfig = field(default_factory=ServerConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    file_injection: FileInjectionConfig = field(default_factory=FileInjectionConfig)
    emotion: EmotionConfig = field(default_factory=EmotionConfig)
    speech: SpeechConfig = field(default_factory=SpeechConfig)
    react: ReactConfig = field(default_factory=ReactConfig)
    executor: ExecutorConfig = field(default_factory=ExecutorConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    skills: SkillConfig = field(default_factory=SkillConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    mcp: MCPConfig = field(default_factory=resolve_mcp_config)

    @classmethod
    def from_env(cls, user_id: str | None = None) -> AppConfig:
        """Build a default ``AppConfig``, optionally overriding ``paths.user_id``.

        Args:
            user_id (str | None): When set, returns a new config whose
                ``PathConfig.user_id`` is this value; other sections use defaults.

        Returns:
            Immutable ``AppConfig`` instance.
        """
        cfg = cls()
        if user_id:
            return cls(paths=PathConfig(user_id=user_id))
        return cfg
