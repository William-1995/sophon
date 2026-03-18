---
name: search
description: Web search via DuckDuckGo. Use for real-time info, news, or when user asks to "search" or "look up".
metadata:
  type: primitive
  dependencies: ""
---

## Tools

### search
Search the web. Returns title, link, snippet per result.
- query (str, required): Search query
- num (int, optional): Max results 1–10, default 5
