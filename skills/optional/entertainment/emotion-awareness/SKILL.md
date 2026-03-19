---
name: emotion-awareness
description: >
  Retrieves pre-analyzed emotion summaries from the database. The orb ring color
  expresses the user's perceived emotion (red=frustrated/disappointed, green=satisfied).
  Use when the user wants emotional trajectory, mood changes, or asks about orb/ring color.
metadata:
  type: feature
  entry_action: run
  dependencies: "time"
---

## Orchestration Guidance

**What it does:** Queries stored emotion segments (user_summary, system_summary, emotion_label). These are computed by an LLM sub-agent that perceives user emotion from their actual questions and replies after each chat run. **Default: all sessions by time**, not filtered by session.

**When to use:**
- User asks whether you can perceive/sense their emotions → call run to demonstrate with actual data
- User asks about their mood, emotional state, or emotional changes over time
- User wants a reflection on "what happened" from an emotional angle
- User asks about the orb/avatar visual state or ring color → the orb ring expresses **their** perceived emotion; call run if needed, then explain using the orb ring color mapping below

**Rules:**
- Do NOT call capabilities.list for emotion questions; call this skill directly
- One call is enough. Default scope=all retrieves across all sessions by time.
- For time expressions ("last week", "yesterday", "past 3 days"): call `time.calculate` first, then `run` with scope=range, since, until.

**Response style:** When presenting emotion insights to the user, **always use natural, human-like tone**. Be warm, empathetic, and conversational. Avoid robotic, clinical, or overly formal phrasing. Match the nuance and sensitivity appropriate to emotional topics.

## What is color?

We use color to express current user's emotions, so the color represent user's emotion, not your emotion.

- **Green** = satisfied, relieved, or amused
- **Gray** = neutral or unknown
- **Orange** = frustrated
- **Red** = disappointed
- **Yellow** = anxious
- **Amber** = confused

Full mapping:

| emotion_label | Ring color | Hex |
|---------------|------------|-----|
| satisfied, relieved, amused | Green | #22c55e |
| neutral | Gray | #94a3b8 |
| frustrated | Orange | #f97316 |
| disappointed | Red | #ef4444 |
| anxious | Yellow | #eab308 |
| confused | Amber | #f59e0b |
| (other) | Gray (default) | #94a3b8 |

## Tools

### run
Retrieve emotion segments. Single entry point; no sub-agent loop.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| scope | string | No | "all" (default) = all sessions by time; "recent_hours" = last N hours; "range" = since/until; "session" = current session only |
| since | string | For scope=range | Start date: YYYY-MM-DD or Unix timestamp |
| until | string | For scope=range | End date: YYYY-MM-DD or Unix timestamp |
| hours | number | No | For scope=recent_hours, look back hours (default: 168 = 7 days) |
| limit | number | No | Max segments (default: 50) |

Returns: segments, count, observation. session_id optional (required only for scope=session). For scope=range, call time.calculate first to resolve natural language to since/until.

## Output Contract

| Field | Type | Description |
|-------|------|-------------|
| segments | array | List of emotion segment dicts |
| count | integer | Number of segments returned |
| observation | string | Human-readable summary for the LLM |
| error | string | Present only on failure |
