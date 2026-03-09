---
name: deep-recall
description: Memory recall and history exploration. Use for any question about past conversations, previous topics, what the user asked before, or recent activity. Replaces the memory skill.
metadata:
  type: primitive
  dependencies: "time"
---

## Orchestration Guidance

**RULE: time expressions ("last week", "yesterday", "past week", "recent") → call `time.calculate` first, then `deep-recall.analyze`. NEVER call `search` for time-based queries.**

**NEVER** tell the user you cannot access history without first calling a `deep-recall` action.

Use `deep-recall` whenever the user asks about past conversations, previous topics, or recent activity.

### Decision tree:

- **Time-based** ("last week", "yesterday", "recent", "past N days", "past week"):
  1. `time.calculate` → get `since`/`until` timestamps
  2. `deep-recall.analyze(since, until)` → retrieve messages
  3. Summarize

- **Topic-based** (specific keyword or technology name):
  1. `deep-recall.search(keyword)` — `keyword` is REQUIRED
  2. Summarize

- **Session-specific** (has session ID):
  1. `deep-recall.detail(session_id)`

- **Open-ended / unsure**:
  1. `deep-recall.explore` → then pick time-based or topic-based

## Tools

### explore
RLM-style exploration. Loads session metadata into a variable map and returns available tool descriptions so the LLM can decide the next step. Use when the user asks an open-ended memory question and you need to orient first.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| query | string | Yes | Natural language question about memory |
| session_hint | string | No | Optional session ID to start from |
| max_depth | int | No | Maximum recursion depth (default: 3) |

Returns: session list, total message count, available tools.

### search
Keyword search across all conversation history. Fast path for topic-based recall.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| keyword | string | Yes | Keyword or phrase to search |
| limit | int | No | Max results (default: return all matches) |

Returns: matching messages with session ID, role, content, and timestamp.

### detail
Retrieve the complete message history for a specific session.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| session_id | string | Yes | Session ID to retrieve |

Returns: All messages in the session, ordered by time.

### analyze
Retrieve and aggregate all messages within a time range. Use this for "summarize last week" or "what happened on Monday" type questions.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| since | string | Yes | Start date: YYYY-MM-DD or Unix timestamp |
| until | string | Yes | End date: YYYY-MM-DD or Unix timestamp |

Returns: All messages in the range with session ID, role, content, and timestamp.

## Output Contract

| Field | Type | Description |
|-------|------|-------------|
| results / messages | array | List of matched messages or session messages |
| count | integer | Number of items returned |
| error | string | Present only on failure |
