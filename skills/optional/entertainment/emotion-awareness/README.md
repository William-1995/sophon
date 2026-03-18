# Emotion-Awareness Skill

Query pre-analyzed emotion summaries. Orb ring color reflects user perceived emotion.

## Capabilities

- **run**: Query emotion segments by scope (all, recent_hours, session)

## Pip Packages

None. Analysis done by Sophon background sub-agent (LLM), persisted in DB.

## Role

- Orb ring color reflects user emotion (green=satisfied, orange=frustrated, red=disappointed)
- User asks about mood, emotional trajectory → return emotion summary

## Notes

- Requires `SOPHON_EMOTION_ENABLED` (default on)
- Data from LLM analysis of user questions and replies
