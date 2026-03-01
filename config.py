"""
V7 Configuration - Sophon Simplified Agent Platform.

Centralized configuration. All paths derived from ROOT.
"""

from dataclasses import dataclass, field
from pathlib import Path

from constants import DB_FILENAME

ROOT = Path(__file__).resolve().parent
DEFAULT_USER_ID = "default_user"
SESSION_ID_LENGTH = 8


@dataclass(frozen=True)
class PathConfig:
    """Path configuration - workspace and DB paths per user."""

    user_id: str = DEFAULT_USER_ID
    workspace: Path = field(default_factory=lambda: ROOT / "workspace")

    def user_workspace(self) -> Path:
        return self.workspace / self.user_id

    def db_path(self) -> Path:
        """SQLite database path per user: workspace/{user}/"""
        return self.user_workspace() / DB_FILENAME

    def recent_files_path(self) -> Path:
        """Path to recent files metadata (stored in SQLite recent_files table)."""
        return self.db_path()

    def ensure_dirs(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.user_workspace().mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ReactConfig:
    """ReAct engine configuration."""

    max_rounds: int = 5
    max_tokens_per_response: int = 4096


@dataclass(frozen=True)
class MemoryConfig:
    """Memory configuration."""

    cache_max_entries: int = 1000
    history_recent_count: int = 10
    recent_files_days: int = 7
    referent_context_rounds: int = 3
    """For referent resolution (e.g. 'my question', 'write to file'), limit context to the most recent N rounds (1 round = 1 user + 1 assistant message). Older messages are excluded from the prompt to avoid confusion."""


@dataclass(frozen=True)
class SkillConfig:
    """Skill configuration - entry points exposed to users (no hardcoding in loader)."""

    exposed_skills: tuple[str, ...] = ("troubleshoot", "deep-research", "search", "filesystem")


@dataclass(frozen=True)
class LLMConfig:
    """LLM provider configuration."""

    default_model: str = "deepseek-chat"
    """Default model for chat. qwen-plus -> Qwen/DashScope, deepseek-chat -> DeepSeek."""


@dataclass(frozen=True)
class MCPServerConfig:
    """Configuration for a single MCP server connection."""

    name: str
    """Server identifier used as tool name prefix (e.g. 'ddg' -> ddg_search)."""
    command: str
    """Executable to spawn (e.g. 'uvx' or 'python')."""
    args: tuple[str, ...]
    """Arguments for the command (e.g. ['duckduckgo-mcp-server'])."""
    load_at_startup: bool = True
    """If True, connect at startup; if False, connect on demand."""

    def tool_prefix(self) -> str:
        """Returns the prefix for tool names, e.g. 'ddg_'."""
        return f"{self.name}_"


@dataclass(frozen=True)
class MCPConfig:
    """MCP client configuration - external MCP servers to use as tools.

    Default uses python -m for portability. Users with uv can use:
    command="uvx", args=("duckduckgo-mcp-server",).
    """

    servers: tuple[MCPServerConfig, ...] = (
        # MCPServerConfig(
        #     name="ddg",
        #     command="python",
        #     args=("-m", "duckduckgo_mcp_server.server"),
        #     load_at_startup=True,
        # ),
    )


@dataclass(frozen=True)
class AppConfig:
    """Complete application configuration."""

    paths: PathConfig = field(default_factory=PathConfig)
    react: ReactConfig = field(default_factory=ReactConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    skills: SkillConfig = field(default_factory=SkillConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)

    @classmethod
    def from_env(cls, user_id: str | None = None) -> "AppConfig":
        cfg = cls()
        if user_id:
            return cls(paths=PathConfig(user_id=user_id))
        return cfg


# Mutable container avoids global keyword (we mutate in place, never rebind).
_config: list[AppConfig] = []


def get_config(user_id: str | None = None) -> AppConfig:
    """Returns app config, lazily created on first call."""
    if not _config:
        _config.append(AppConfig.from_env(user_id))
    return _config[0]


def bootstrap(user_id: str | None = None) -> None:
    """Initialize app: ensure dirs, init DB. Call once at startup."""
    cfg = get_config(user_id)
    cfg.paths.ensure_dirs()
