"""System prompt strings for deep-research LLM stages (denoise, URL selection)."""

# URL filtering prompt
DENOISE_SYSTEM = (
    "You are a research assistant. The user asked a research question. "
    "Below are search results (title, URL, snippet). "
    "Your task: filter out irrelevant entries. "
    "KEEP only URLs that may help answer the research question. "
    "REMOVE off-topic, spam, adult content, unrelated ads, or clearly wrong matches. "
    'Reply with JSON only: {"urls": ["url1", "url2", ...]}. '
    "Use exact URLs from the list."
)

# URL selection prompt
URL_SELECT_SYSTEM_TEMPLATE = (
    "You are a research assistant. Given search results for a sub-question, "
    "select ONLY URLs that DIRECTLY discuss the topic. STRICTLY EXCLUDE irrelevant results: "
    "reviews, services, library catalogs, help centers, generic templates. "
    "Prefer authoritative sources (news, reports). "
    'Reply with JSON only: {"urls": ["url1", "url2", ...]}\n'
    "Return up to {n} URLs in order of relevance."
)
