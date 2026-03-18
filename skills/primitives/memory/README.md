# Memory Skill

Memory recall and history exploration. Use for any question about past conversations, previous topics, or recent activity.

## Capabilities

- **explore**: RLM-style exploration — session index, then pick search/analyze/detail
- **search**: Keyword search across conversation history
- **detail**: Full conversation for a specific session
- **analyze**: Messages within a time range (since/until)

## Dependencies

- **time** skill: For relative dates ("last week", "yesterday"), call `time.calculate` first.

## Role

- Recall prior discussions
- Time-based queries → `time.calculate` then `memory.analyze`
- Topic-based → `memory.search(keyword)`
- Open-ended → `memory.explore` first
