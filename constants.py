"""
Constants - Centralized literals and limits. No magic numbers in business logic.
"""

from enum import StrEnum

from config.common import (
    CAPABILITIES_SKILL_NAME,
    DB_FILENAME,
    DEFAULT_API_PORT,
    DEFAULT_USER_ID,
    PROFILE_IMAGE_FILENAME,
    ROOT,
    SESSION_ID_LENGTH,
    SOPHON_IMAGE_FILENAME,
    WORKSPACE_UPLOAD_MAX_BYTES,
    WORKSPACE_DOCS_DIR,
    WORKSPACE_IMAGES_DIR,
    WORKSPACE_PROFILE_DIR,
)
from config.defaults import DEFAULT_MODEL, SKILL_TIMEOUT, SKILL_TIMEOUT_OVERRIDES

# ── API Metadata ───────────────────────────────────────────────────────────────
API_TITLE = "Sophon"
API_VERSION = "0.2.0"
API_DESCRIPTION = "AI agent platform with ReAct loop and skill system"

# ── ReAct: multi-part heuristic when skill_filter is set (no round-1 skill LLM). ASCII tokens only.
REACT_MULTI_PART_CONJUNCTION_PATTERN = r"\b(and|also|then|plus)\b"
REACT_MULTI_PART_LIST_SEPARATOR_PATTERN = r"[,;]\s*(?:\w|@)"

# ── LLM Models ─────────────────────────────────────────────────────────────────

# ── Content display limits (characters) ──────────────────────────────────────
MAX_CONTENT_PREVIEW = 1000
MAX_LOG_LINE_LENGTH = 500
MAX_RESULT_PREVIEW = 500
DEFAULT_LOG_LIMIT = 100
MAX_LOG_LIMIT = 5000

# ── Timeouts (seconds) ────────────────────────────────────────────────────────
LLM_TIMEOUT = 1200  # HTTP read timeout for LLM chat (local/Ollama models, including emotion sub-agent)
# Transient HTTP failures (incomplete chunked body, reset, etc.): retry count for provider.chat
LLM_HTTP_MAX_ATTEMPTS = 4
LLM_HTTP_RETRY_BASE_DELAY = 0.75

# ── ReAct loop ────────────────────────────────────────────────────────────────
DEFAULT_MAX_ROUNDS = 5
# When the model returns no tool calls and there are no observations yet, inject a
# force-tool user message and continue (max times per run) instead of summarizing empty results.
REACT_MAX_EMPTY_TOOL_FORCE = 3

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
# Inside __decision_request "payload": when True and run state has plan_confirmed, executor picks confirm without UI
DECISION_PAYLOAD_AUTO_CONFIRM_IF_PLAN_CONFIRMED = "auto_confirm_if_plan_confirmed"


class SophonSkillEventType(StrEnum):
    """Well-known skill IPC event types. Orchestration matches on type only—no skill-name checks."""

    PLAN_CONFIRMED = "PLAN_CONFIRMED"

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
# Seconds to add to midnight of a parsed YYYY-MM-DD to include that full calendar day
END_OF_DAY_INCLUSIVE_OFFSET_SECONDS = SECONDS_PER_DAY - 1
# Prefix length for ISO date-only strings "YYYY-MM-DD"
ISO_DATE_YYYY_MM_DD_LEN = 10
# Prefix length for naive "YYYY-MM-DDTHH:MM:SS" (no timezone)
ISO_LOCAL_DATETIME_NO_TZ_LEN = 19

# ── SQL patterns for primitives ────────────────────────────────────────────────
SQL_DEFAULT_LIMIT = 200
SQL_DATE_FORMAT = "%Y-%m-%d"
SQL_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# ── Emotion awareness (optional feature) ─────────────────────────────────────────
EMOTION_USER_WEIGHT_DEFAULT = 0.8
EMOTION_SYSTEM_WEIGHT_DEFAULT = 0.2
EMOTION_RECENT_HOURS_DEFAULT = 2.0
# scripts/run.py — DB retrieval defaults and observation preview
EMOTION_RUN_DEFAULT_SEGMENT_LIMIT = 50
EMOTION_RUN_DEFAULT_RECENT_HOURS = 168.0  # seven days for scope=recent_hours default
EMOTION_RUN_OBSERVATION_PREVIEW_COUNT = 5
EMOTION_RUN_OBSERVATION_SUMMARY_MAX_CHARS = 200
# scripts/_lib/analyzer.py — segment building and LLM fallback
EMOTION_ANALYZER_SEGMENT_MAX_CHARS = 4000
EMOTION_ANALYZER_TRACE_PREVIEW_LEN = 80
EMOTION_ANALYZER_FALLBACK_SUMMARY_MAX_CHARS = 500
EMOTION_ANALYZER_TRACE_LINES_IN_SEGMENT_MAX = 15
EMOTION_ANALYZER_MESSAGES_IN_RANGE_LIMIT = 20

# ── Cross-cutting: skill progress events, search/crawl, trace/log tools ───────────
PROGRESS_URL_DISPLAY_MAX_CHARS = 80
PROGRESS_SEARCH_QUERY_DISPLAY_MAX_CHARS = 60
SEARCH_DEFAULT_MAX_RESULTS = 5
SEARCH_CAP_MAX_RESULTS = 10
SEARCH_MIN_MAX_RESULTS = 1
CRAWLER_DEFAULT_WAIT_FOR_MS = 2000
TRACE_ANALYZE_SLOWEST_OPS_COUNT = 10
TRACE_ANALYZE_ERROR_SAMPLE_MAX = 20
TRACE_ANALYZE_DEFAULT_ROW_LIMIT = 1000
LOG_ANALYZE_DEFAULT_ROW_LIMIT = 10000
LOG_ANALYZE_DEFAULT_RANGE_DAYS = 7
# memory detail observation lines + memory analyze JSON content previews
MEMORY_USER_CONTENT_SNIPPET_MAX_CHARS = 200
SKILL_BRIEF_IN_PROMPT_MAX_CHARS = 180
TASK_PLAN_QUESTION_LOG_PREVIEW_MAX = 80
TASK_PLAN_TOOLS_BRIEF_MAX_ITEMS = 40
TASK_PLAN_TOOL_DESCRIPTION_TRUNCATE = 120
REACT_SKILL_RESULT_DEBUG_PREVIEW_MAX = 200
CHECKPOINT_QUESTION_PREVIEW_MAX = 500
REACT_CANCEL_CHECKPOINT_OBS_PREVIEW_MAX = 2000
DEEP_RESEARCH_ERROR_PREVIEW_MAX_CHARS = 120
DEEP_RESEARCH_SOURCE_TEXT_PREVIEW_MAX_CHARS = 800
PERSONAL_WORKBENCH_QUESTION_LOG_PREVIEW_MAX = 100
API_WORKSPACE_DISPLAY_PARTS_MAX = 4
API_WORKSPACE_UPLOAD_FILENAME_MAX_CHARS = 240
ASYNC_TASK_ANSWER_SUMMARY_MAX = 120
CHECKPOINT_QUESTION_STORE_MAX = 2000
CHECKPOINT_QUESTION_READ_PREVIEW_MAX = 200
RUN_CHECKPOINT_LIST_DEFAULT_LIMIT = 20
OPENAI_COMPAT_CHATCMPL_ID_RANDOM_HEX_LEN = 24
API_MESSAGE_ID_RANDOM_HEX_SUFFIX_LEN = 12
MEMORY_CACHE_QUESTION_HASH_HEX_LEN = 32
# Framed IPC: big-endian uint32 length prefix before JSON payload
IPC_MESSAGE_LENGTH_PREFIX_BYTES = 4
