---
name: memory
description: Retrieve past conversations. Use for prior dialogue, past questions, or history lookup.
metadata:
  type: primitive
  dependencies: "time"
---

## Orchestration Guidance

**Short-term first, long-term second**: For recall ("what did we discuss about X"), prefer recent context. memory.search automatically queries current session first, then expands to cross-session. memory.read defaults to current session when date and session_id omitted.

Use search for keyword lookup; use read for a specific date or session. Omit session_id to use current session (short-term).

**Resolving referents**: When the user refers to "my question", "what I asked", "the previous message", "that content", etc. without stating it explicitly, prioritize the most recent rounds of dialogue (default 3 rounds; configurable via referent_context_rounds). Only the most recent N rounds are passed to you, so use them first. Call memory.read (omit session_id for current session) if you need more. If you cannot determine the referent confidently, ask the user to clarify before acting.

For relative dates (yesterday, 2 days ago, day before yesterday): call time.calculate first. Use its since/until (extract YYYY-MM-DD) as memory.search(date_range={"start": since_date, "end": until_date}) or memory.read(date=since_date).

## Tools

### search
Search memory by keywords. Short-term (current session) first, then long-term (cross-session).
- query (str, optional): Search keywords. Omit for date-only filter.
- session_id (str, optional): Prefer this session (short-term). Omit to use current session first.
- date_range (object, optional): {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}. Also accepts [start, end] from time.calculate.
- top_k / limit (int, optional): Number of results. Default from config (memory_search_default_limit, typically 200). LLM can override for sliding-window or narrow scope.

### read
Read complete memory. Defaults to current session (short-term) when date and session_id omitted.
- date (str, optional): YYYY-MM-DD, today, yesterday
- session_id (str, optional): Omit to use current session
- limit (int, optional): Max results, default 50
- order (str, optional): "asc" (oldest first, default for full conversation) or "desc"/"newest" (newest first)

### summarize
Summarize memory over a period.
- since (str, required): Start date YYYY-MM-DD
- until (str, required): End date YYYY-MM-DD
- focus (str, optional): Focus topic to filter
