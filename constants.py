"""
Constants - Centralized literals and limits. No magic numbers in business logic.
"""

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

# Lightweight LLM eval: only look at the last N observations
EVAL_OBSERVATION_PREVIEW_LEN = 400
EVAL_OBSERVATIONS_TAIL = 5

# Deep-research sub-agent
DEEP_RESEARCH_MAX_ROUNDS = 10

# ── SKILL.md spec limits (agentskills.io / Anthropic) ────────────────────────
SKILL_NAME_MAX_LEN = 64
SKILL_DESCRIPTION_MAX_LEN = 1024
SKILL_COMPATIBILITY_MAX_LEN = 500
