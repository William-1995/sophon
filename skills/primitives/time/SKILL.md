---
name: time
description: Date ranges, timezone conversion, timestamp formatting.
metadata:
  type: primitive
  dependencies: ""
---

## Tools

### calculate
Convert natural language to date range. Returns since/until (ISO). Use for resolving relative dates before calling memory, log-analyze, etc.
- expression (str): e.g. "today", "yesterday", "2 days", "7 days", "5h". "2 days" = day before yesterday; extract YYYY-MM-DD from since for memory.read(date=...)

### convert
Convert timestamp between timezones.
- timestamp (str)
- from_tz (str, optional)
- to_tz (str, optional)

### format
Format timestamp to string.
- timestamp (str)
- format (str, optional)
