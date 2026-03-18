"""
Workbook (xlsx and supersets) ops skill configuration. No magic numbers or hardcoded column/sheet names.
"""

# Skill and dependencies (centralized; do not hardcode in scripts)
SKILL_NAME = "excel-ops"
DEPENDENCY_SKILL_EXCEL = "excel"
DEPENDENCY_SKILL_SEARCH = "search"
DEPENDENCY_SKILL_CRAWLER = "crawler"

# Sub-agent name (run entry invokes this flow; more workbook ops can be added later)
SUBAGENT_DEEP_EXCEL_RESEARCH = "deep-excel-research"

# Retrieve mode: "search" (snippets only), "crawl" (fetch URL page), "auto" (crawl if URL-like else search)
RETRIEVE_MODE_SEARCH = "search"
RETRIEVE_MODE_CRAWL = "crawl"
RETRIEVE_MODE_AUTO = "auto"
RETRIEVE_MODE_DEFAULT = RETRIEVE_MODE_AUTO

# Rows (1-based; header row is 1, first data row is START_ROW_DATA_DEFAULT)
START_ROW_DATA_DEFAULT = 2
DEFAULT_SAMPLE_ROWS = 2
MAX_SAMPLE_ROWS = 20

# Batching
DEFAULT_BATCH_SIZE = 5
MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 20

# Search
SEARCH_NUM_RESULTS = 5
CONTENT_PREVIEW_LEN = 8000  # chars per row in LLM batch prompt

# Output
OUTPUT_SUFFIX_FILLED = "_FILLED"
OUTPUT_SUFFIX_ENRICHED = "_ENRICHED"
MODE_COPY = "copy"
MODE_OVERWRITE = "overwrite"

# Extraction (LLM) — generic; no column or row names. Caller passes target_columns and instructions.
DEFAULT_EXTRACT_INSTRUCTIONS = (
    "Infer values from the search content for each target column. "
    "Fill every target column when the content allows; use empty string when information is absent or uncertain. "
    "Prefer concrete, specific values over generic or code-only text where applicable."
)

# Enrich LLM prompts (used by _batch.py)
ENRICH_DEFAULT_INSTRUCTIONS_TEMPLATE = (
    "Infer values from the search content for each target column: {target_columns}. "
    "Fill every target column when the content allows; use empty string when information is absent or uncertain. "
    "Prefer concrete, specific values over generic or code-only text where applicable."
)

ENRICH_LLM_PROMPT_TEMPLATE = (
    "You are a data extraction assistant. Given search results for multiple rows, "
    "extract the requested information for each row.\n\n"
    "Target columns: {target_columns}\n\n"
    "Instructions: {instructions}\n\n"
    "Batch data:\n{batch_data}\n\n"
    "Return a JSON array, one object per row with the extracted values. "
    "Use exact column names as keys. If information is not available, use empty string."
)

ENRICH_SYSTEM_PROMPT = (
    "You are a data extraction assistant. Extract structured information from search results. "
    "Return valid JSON array only."
)
