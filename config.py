"""
Sophon Configuration - Simplified Agent Platform.

Centralized configuration. All paths derived from ROOT.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from constants import (
    DB_FILENAME,
    DEFAULT_USER_ID,
    PROFILE_IMAGE_FILENAME,
    SOPHON_IMAGE_FILENAME,
    WORKSPACE_DOCS_DIR,
    WORKSPACE_IMAGES_DIR,
    WORKSPACE_PROFILE_DIR,
)

ROOT = Path(__file__).resolve().parent
SESSION_ID_LENGTH = 8


@dataclass(frozen=True)
class PathConfig:
    """Path configuration - workspace and DB paths per user.

    Workspace layout: workspace/{user_id}/
      - docs/           All user documents (file ops default here)
      - images/         Media assets
      - images/profile/ Profile image for orb avatar (avatar.png)
      - sophon.db       SQLite database
    """

    user_id: str = DEFAULT_USER_ID
    workspace: Path = field(default_factory=lambda: ROOT / "workspace")

    def user_workspace(self) -> Path:
        return self.workspace / self.user_id

    def docs_dir(self) -> Path:
        """Documents directory. Default root for file operations."""
        return self.user_workspace() / WORKSPACE_DOCS_DIR

    def images_dir(self) -> Path:
        """Images directory."""
        return self.user_workspace() / WORKSPACE_IMAGES_DIR

    def profile_dir(self) -> Path:
        """Profile images (e.g. orb avatar)."""
        return self.user_workspace() / WORKSPACE_PROFILE_DIR

    def profile_image_path(self) -> Path:
        """Path to user profile image (me.jpeg)."""
        return self.profile_dir() / PROFILE_IMAGE_FILENAME

    def sophon_image_path(self) -> Path:
        """Path to Sophon avatar (sophon.jpeg)."""
        return self.profile_dir() / SOPHON_IMAGE_FILENAME

    def db_path(self) -> Path:
        """SQLite database path per user: workspace/{user}/"""
        return self.user_workspace() / DB_FILENAME

    def recent_files_path(self) -> Path:
        """Path to recent files metadata (stored in SQLite recent_files table)."""
        return self.db_path()

    def ensure_dirs(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.user_workspace().mkdir(parents=True, exist_ok=True)
        self.docs_dir().mkdir(parents=True, exist_ok=True)
        self.images_dir().mkdir(parents=True, exist_ok=True)
        self.profile_dir().mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ReactConfig:
    """ReAct engine configuration."""

    max_rounds: int = 5
    max_tokens_per_response: int = 4096
    max_parallel_tool_calls: int = 10
    """Cap concurrent tool executions per round. Prevents resource exhaustion from LLM hallucination."""
    hitl_enabled: bool = field(
        default_factory=lambda: os.environ.get("SOPHON_HITL_ENABLED", "true").lower() in ("1", "true", "yes")
    )
    """When True, adds request_human_decision tool for human-in-the-loop. Disable via SOPHON_HITL_ENABLED=0."""
    thinking_enabled: bool = field(
        default_factory=lambda: os.environ.get("SOPHON_THINKING_ENABLED", "true").lower() in ("1", "true", "yes")
    )
    """When True, prompts LLM to wrap reasoning in <thinking>...</thinking>; parsed and emitted as THINKING events. Disable via SOPHON_THINKING_ENABLED=0."""


@dataclass(frozen=True)
class ExecutorConfig:
    """Executor configuration - timeouts and parameter injection."""

    default_timeout: int = 30
    """Default skill script timeout (seconds). Override via constants.SKILL_TIMEOUT_OVERRIDES."""
    timeout_overrides: tuple[tuple[str, int], ...] = ()  # (skill_name, seconds)
    """Per-skill timeout overrides. Populated from constants.SKILL_TIMEOUT_OVERRIDES."""


def _executor_timeout_overrides() -> tuple[tuple[str, int], ...]:
    """Load timeout overrides from constants (configurable via constants module)."""
    from constants import SKILL_TIMEOUT_OVERRIDES
    return tuple(SKILL_TIMEOUT_OVERRIDES.items())


def get_executor_param_injections(skill_name: str, action: str) -> dict:
    """Return extra params to merge into skill args. Config-driven; no hardcoding in executor."""
    cfg = get_config()
    if skill_name == "memory" and action == "search":
        return {"_memory_search_default_limit": cfg.memory.memory_search_default_limit}
    return {}


@dataclass(frozen=True)
class MemoryConfig:
    """Memory configuration."""

    cache_max_entries: int = 1000
    history_recent_count: int = 10
    recent_files_days: int = 7
    referent_context_rounds: int = 3
    """For referent resolution (e.g. 'my question', 'write to file'), limit context to the most recent N rounds (1 round = 1 user + 1 assistant message). Older messages are excluded from the prompt to avoid confusion."""
    memory_search_default_limit: int = field(
        default_factory=lambda: int(os.environ.get("SOPHON_MEMORY_SEARCH_DEFAULT_LIMIT", "200"))
    )
    """Default top_k/limit for memory.search when LLM does not specify. Override via SOPHON_MEMORY_SEARCH_DEFAULT_LIMIT env."""


@dataclass(frozen=True)
class SkillConfig:
    """Skill configuration - entry points exposed to users (no hardcoding in loader)."""

    exposed_skills: tuple[str, ...] = (
        "troubleshoot",
        "deep-research",
        "excel-ops",
        "search",
        "crawler",
        "filesystem",
        "deep-recall",
    )
    internal_skills: tuple[str, ...] = ("capabilities",)
    """Skills always available to the agent but NOT shown in frontend. E.g. capabilities (list what you can do)."""


@dataclass(frozen=True)
class DeepResearchConfig:
    """Deep research sub-agent configuration."""

    urls_per_sub_question: int = 10
    """Max URLs to fetch per sub-question after LLM selection."""
    crawler_concurrency: int = 3
    """Max concurrent crawler.scrape calls. Playwright is resource-heavy."""


def _resolve_deep_research_config() -> DeepResearchConfig:
    import os
    urls = int(os.environ.get("SOPHON_DEEP_RESEARCH_URLS", "10"))
    concurrency = int(os.environ.get("SOPHON_DEEP_RESEARCH_CRAWLER_CONCURRENCY", "3"))
    return DeepResearchConfig(urls_per_sub_question=urls, crawler_concurrency=concurrency)


@dataclass(frozen=True)
class LLMConfig:
    """LLM provider configuration."""

    default_model: str = "deepseek-chat"
    """Default model for chat. qwen-plus -> Qwen/DashScope, deepseek-chat -> DeepSeek."""


@dataclass(frozen=True)
class SpeechConfig:
    """Local speech-to-text (faster-whisper) configuration."""

    enabled: bool = field(
        default_factory=lambda: os.environ.get("SOPHON_SPEECH_ENABLED", "1").lower() in ("1", "true", "yes")
    )
    """Enable local STT. Default on. Set SOPHON_SPEECH_ENABLED=0 to disable."""
    model: str = field(
        default_factory=lambda: os.environ.get("SOPHON_SPEECH_MODEL", "base")
    )
    """faster-whisper model: tiny, base, small, medium, large."""
    language: str | None = field(
        default_factory=lambda: os.environ.get("SOPHON_SPEECH_LANGUAGE") or None
    )
    """zh, en, or None for auto."""
    device: str = field(
        default_factory=lambda: os.environ.get("SOPHON_SPEECH_DEVICE", "cpu")
    )
    """cpu or cuda."""
    compute_type: str = field(
        default_factory=lambda: os.environ.get("SOPHON_SPEECH_COMPUTE", "int8")
    )
    """int8 for CPU, float16 for GPU."""


@dataclass(frozen=True)
class MCPServerConfig:
    """Configuration for a single MCP server connection."""

    name: str
    """Server identifier used as tool name prefix (e.g. 'firecrawl' -> firecrawl_scrape)."""
    command: str
    """Executable to spawn (e.g. 'npx' or 'python')."""
    args: tuple[str, ...]
    """Arguments for the command (e.g. ['-y', 'firecrawl-mcp'])."""
    load_at_startup: bool = True
    """If True, connect at startup; if False, connect on demand."""
    env: tuple[tuple[str, str], ...] = ()
    """Extra env vars (key, value) for subprocess. Values support {name} from env."""

    def tool_prefix(self) -> str:
        """Returns the prefix for tool names, e.g. 'firecrawl_'."""
        return f"{self.name}_"


def _mcp_default_servers() -> tuple[MCPServerConfig, ...]:
    """Build MCP servers. Default crawler uses Playwright (no MCP). Optional: Firecrawl when API key set."""
    import os
    servers: list[MCPServerConfig] = []
    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if firecrawl_key:
        servers.append(
            MCPServerConfig(
                name="firecrawl",
                command="npx",
                args=("-y", "firecrawl-mcp"),
                load_at_startup=True,
                env=(("FIRECRAWL_API_KEY", firecrawl_key),),
            )
        )
    return tuple(servers)


@dataclass(frozen=True)
class MCPConfig:
    """MCP client configuration - external MCP servers used by skills.

    MCP tools are NOT exposed to the main agent; only skills with metadata.mcp
    can call them via the internal bridge.
    """

    servers: tuple[MCPServerConfig, ...] = ()
    """Populated by _mcp_default_servers() when config is built."""

    bridge_base_url: str = ""
    """Base URL for MCP bridge (e.g. http://127.0.0.1:8080). Skill subprocesses POST here.
    Default: SOPHON_MCP_BRIDGE_URL or http://127.0.0.1:8080."""


def _resolve_mcp_config() -> MCPConfig:
    """Build MCPConfig with env-driven servers.

    Bridge URL is resolved lazily via mcp_integration.bridge_server.get_bridge_base_url()
    (runs on a dedicated port to avoid deadlock when skills call MCP).
    """
    return MCPConfig(servers=_mcp_default_servers(), bridge_base_url="")


@dataclass(frozen=True)
class AppConfig:
    """Complete application configuration."""

    paths: PathConfig = field(default_factory=PathConfig)
    speech: SpeechConfig = field(default_factory=SpeechConfig)
    react: ReactConfig = field(default_factory=ReactConfig)
    executor: ExecutorConfig = field(default_factory=lambda: ExecutorConfig(timeout_overrides=_executor_timeout_overrides()))
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    skills: SkillConfig = field(default_factory=SkillConfig)
    deep_research: "DeepResearchConfig" = field(default_factory=_resolve_deep_research_config)
    llm: LLMConfig = field(default_factory=LLMConfig)
    mcp: MCPConfig = field(default_factory=_resolve_mcp_config)

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
