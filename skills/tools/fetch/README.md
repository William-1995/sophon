# Fetch Skill

Simple HTTP GET. Download files or fetch web content.

## Capabilities

- **get**: HTTP GET, returns text or base64 (binary)

## Pip Packages

| Package | Purpose |
|---------|---------|
| `httpx` | HTTP client |

## Role

- Download remote PDF, Word, Excel for parsing
- Simple web fetch (use crawler for complex pages)

## Notes

- Returns `content` (UTF-8) or `content_base64` (binary)
- Use with pdf/word parse: fetch.get → content_base64 → parse
