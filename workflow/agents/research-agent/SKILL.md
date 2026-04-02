---
name: research-agent
description: Performs web research by searching and crawling sources.
metadata:
  type: agent
  dependencies: "search,crawler"
---

## Capabilities

- Web search using DuckDuckGo
- Content crawling with Playwright
- URL extraction and ranking
- Structured result output

## Input Schema

```json
{
  "query": "string - Research topic or question",
  "max_sources": "number - Maximum sources to crawl (default: 3)"
}
```

## Output Schema

```json
{
  "query": "string",
  "sources_found": "number",
  "sources_crawled": "number",
  "urls": ["string"],
  "crawled_data": [
    {
      "url": "string",
      "content": "string"
    }
  ],
  "summary": "string"
}
```