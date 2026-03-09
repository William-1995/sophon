"""
Constants - Centralized literals and limits. No magic numbers in business logic.
"""

# ── API Metadata ───────────────────────────────────────────────────────────────
API_TITLE = "Sophon"
API_VERSION = "0.1.0"
API_DESCRIPTION = "AI agent platform with ReAct loop and skill system"

# ── Default User ───────────────────────────────────────────────────────────────
DEFAULT_USER_ID = "default_user"

# ── LLM Models ─────────────────────────────────────────────────────────────────
DEFAULT_MODEL = "deepseek-chat"

# ── Database ──────────────────────────────────────────────────────────────────
DB_FILENAME = "sophon.db"

# ── Content display limits (characters) ──────────────────────────────────────
MAX_CONTENT_PREVIEW = 1000
MAX_LOG_LINE_LENGTH = 500
MAX_RESULT_PREVIEW = 500
DEFAULT_LOG_LIMIT = 100
MAX_LOG_LIMIT = 5000

# ── Timeouts (seconds) ────────────────────────────────────────────────────────
SKILL_TIMEOUT = 30
LLM_TIMEOUT = 60
# Per-skill overrides (heavy skills: multi-LLM, web fetch). Key = skill_name, value = seconds.
SKILL_TIMEOUT_OVERRIDES: dict[str, int] = {
    "deep-research": 300,
    "crawler": 60,
    "excel-ops": 1200,  # Sub-agent + crawl per row
}

# ── ReAct loop ────────────────────────────────────────────────────────────────
DEFAULT_MAX_ROUNDS = 5

# Follow-up message appended to Results when agent loop continues
FOLLOW_UP_MSG = (
    "If you have enough information, provide a concise direct answer. "
    "Otherwise call more tools."
)

# Summarize prompt sent after observations are collected
SUMMARIZE_MSG = (
    "Based on the tool results above, provide a direct final answer to the user. "
    "Do NOT add meta-phrases like 'According to deep research' or similar. "
    "No further tool calls."
)

# ── Tool builder section limits (characters) ──────────────────────────────────
TOOL_WORKSPACE_SECTION_MAX = 400
TOOL_ORCHESTRATION_SECTION_MAX = 1200
TOOL_TOOLS_SECTION_MAX = 1400
TOOL_FALLBACK_SECTION_MAX = 1200
TOOL_ACTION_HINT_MAX = 200

# ── Observation handling ──────────────────────────────────────────────────────
OBSERVATION_PREVIEW_LEN = 800
# Max total chars of "Results:\n" + observations sent to LLM per round
OBSERVATIONS_COMBINED_MAX = 12000

# Lightweight LLM eval: only look at the last N observations
EVAL_OBSERVATION_PREVIEW_LEN = 400
EVAL_OBSERVATIONS_TAIL = 5
# Min observations before running eval; single result rarely needs evaluation
EVAL_MIN_OBSERVATIONS = 2
# Regex to extract satisfied JSON from eval LLM response
EVAL_SATISFIED_JSON_PATTERN = r'\{[^{}]*"satisfied"[^{}]*\}'

# ── File injection (@file auto-read) ───────────────────────────────────────────
FILE_INJECTION_MAX_LEN = 3000  # Max characters per file content injected into context

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_MESSAGE_MAX_LEN = 80  # Max length for message preview in logs

# Deep-research sub-agent
DEEP_RESEARCH_MAX_ROUNDS = 10

# ── Agent loop ──────────────────────────────────────────────────────────────────
AGENT_LOOP_RESULTS_PREFIX = "Results:\n"
AGENT_LOOP_FORCE_TOOL_MSG = (
    "You must call a tool. The task is not complete. "
    "Your next response MUST be a tool call with the correct parameters."
)
AGENT_LOOP_SUMMARIZE_GUIDANCE_PREFIX = "\n\nUse this interpretation guidance:\n"

# ── Executor ──────────────────────────────────────────────────────────────────
EXECUTOR_RESULT_PREVIEW_LEN = 200  # Error log preview
EXECUTOR_TRACE_PREVIEW_LEN = 500
EXECUTOR_EVENT_DRAIN_TIMEOUT = 2.0  # Seconds to wait for event pipe drain after proc exit
IPC_BUFFER_READ_SIZE = 4096

# ── SKILL.md spec limits (agentskills.io / Anthropic) ────────────────────────
SKILL_NAME_MAX_LEN = 64
SKILL_DESCRIPTION_MAX_LEN = 1024
SKILL_COMPATIBILITY_MAX_LEN = 500

# ── Skills/Primitives ──────────────────────────────────────────────────────────
DEFAULT_ENCODING = "utf-8"
DEFAULT_CSV_ENCODING = "utf-8-sig"
DEFAULT_QUERY_LIMIT = 200
DEFAULT_ANALYSIS_LIMIT = 1000
SECONDS_PER_DAY = 86400

# ── SQL patterns for primitives ────────────────────────────────────────────────
SQL_DEFAULT_LIMIT = 200
SQL_DATE_FORMAT = "%Y-%m-%d"
SQL_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
