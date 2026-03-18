---
name: fetch
description: Simple HTTP GET. Returns raw bytes (base64) or text. Use to download files for parsing (PDF, Word, etc.) or when crawler is overkill. Composes with pdf/word/excel parse tools.
metadata:
  type: primitive
  dependencies: ""
---

## Workspace

- No workspace dependency. Pass URL as argument.

## Tools

### get

Fetch URL via HTTP GET. Returns content as text (when UTF-8 decodable) or base64 (for binary). Use for PDF/Word/Excel URLs before parsing.

| Parameter | Type   | Required | Description |
|-----------|--------|----------|-------------|
| url       | string | Yes      | URL to fetch |
| timeout   | int    | No       | Request timeout in seconds (default from constants) |
| max_bytes | int    | No       | Max response body size in bytes (default from constants) |

Returns: `{content?, content_base64?, content_type, status_code, content_length, url}` or `{error}`.
