# Crawler Skill

Web scraping with JavaScript rendering. Single-URL content extraction.

## Capabilities

- **scrape**: Scrape one URL, return main content as Markdown

## Pip Packages

| Package | Purpose |
|---------|---------|
| `playwright` | Headless browser, JS rendering |
| `trafilatura` | Content extraction |

## System Requirements

Install Playwright browser:

```bash
pip install playwright trafilatura
playwright install chromium
```

### Platform Notes

| Platform | Notes |
|----------|-------|
| **macOS / Linux** | `playwright install chromium` usually sufficient |
| **Windows** | Same; use `playwright install` if chromium fails |
| **Docker** | See [Playwright Docker](https://playwright.dev/python/docs/docker) for system deps |

## Role

- Scrape SPAs and dynamic pages
- Used by deep-research, excel-ops
