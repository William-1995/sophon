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

# ── Workspace structure (workspace/{user_id}/) ──────────────────────────────────
WORKSPACE_DOCS_DIR = "docs"
WORKSPACE_IMAGES_DIR = "images"
WORKSPACE_PROFILE_DIR = "images/profile"
PROFILE_IMAGE_FILENAME = "me.jpeg"  # User avatar
SOPHON_IMAGE_FILENAME = "sophon.jpeg"  # Sophon (assistant) avatar

# ── Content display limits (characters) ──────────────────────────────────────
MAX_CONTENT_PREVIEW = 1000
MAX_LOG_LINE_LENGTH = 500
MAX_RESULT_PREVIEW = 500
DEFAULT_LOG_LIMIT = 100
MAX_LOG_LIMIT = 5000

# ── Timeouts (seconds) ────────────────────────────────────────────────────────
SKILL_TIMEOUT = 30
LLM_TIMEOUT = 1200  # HTTP read timeout for LLM chat (local/Ollama models, including emotion sub-agent)
# Per-skill overrides (heavy skills: multi-LLM, web fetch). Key = skill_name, value = seconds.
SKILL_TIMEOUT_OVERRIDES: dict[str, int] = {
    "deep-research": 300,
    "crawler": 60,
    "excel-ops": 1200,  # Sub-agent + crawl per row
    "todos": 60,  # LLM planning + HITL
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
# Compact mode (round 2+): smaller sections to reduce tokens
TOOL_COMPACT_DESC_MAX = 120
TOOL_COMPACT_ORCHESTRATION_MAX = 400
TOOL_COMPACT_TOOLS_SECTION_MAX = 500

# ── Cross-run context (initial history before ReAct) ──────────────────────────
# Condense past Q&A to reduce tokens. Only applies to build_chat_context output.
CONTEXT_USER_BRIEF_MAX = 200  # Max chars per user message in condensed context
CONTEXT_ASSISTANT_BRIEF_MAX = 120  # Max chars per assistant message in condensed context

# ── Observation handling ──────────────────────────────────────────────────────
OBSERVATION_PREVIEW_LEN = 800
# Max total chars of "Results:\n" + observations sent to LLM per round
OBSERVATIONS_COMBINED_MAX = 12000
# When summarizing old rounds: keep this many recent observations in full; older ones get brief form
OBSERVATIONS_KEEP_FULL_TAIL = 3
# Max chars per observation when in "brief" (old-round) form
OBSERVATION_BRIEF_MAX = 80

# Lightweight LLM eval: only look at the last N observations
EVAL_OBSERVATION_PREVIEW_LEN = 400
EVAL_OBSERVATIONS_TAIL = 5
# Min observations before running eval; single result rarely needs evaluation
EVAL_MIN_OBSERVATIONS = 2
# Regex to extract satisfied JSON from eval LLM response
EVAL_SATISFIED_JSON_PATTERN = r'\{[^{}]*"satisfied"[^{}]*\}'

# ── Skill decision request (two-phase confirm flow) ───────────────────────────
# When a skill outputs this key, execution layer triggers HITL and re-invokes with _decision_choice
DECISION_REQUEST_KEY = "__decision_request"

# ── Framework contract: early exit ─────────────────────────────────────────────
# When a skill/sub-agent returns this key as true, the main agent stops immediately.
# Skills opt-in by including _abort_run: true (e.g. user cancelled HITL).
ABORT_RUN_KEY = "_abort_run"

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

# ── Emotion awareness (optional feature) ─────────────────────────────────────────
EMOTION_USER_WEIGHT_DEFAULT = 0.8
EMOTION_SYSTEM_WEIGHT_DEFAULT = 0.2
EMOTION_RECENT_HOURS_DEFAULT = 2.0
