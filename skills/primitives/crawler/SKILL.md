---
name: crawler
description: Web scraping via Playwright. Use when user wants to fetch page content or scrape a URL. 
metadata:
  type: primitive
  dependencies: ""
---

## Workspace

- Runs in the agent workspace; URLs are passed as arguments.

## Tools

### scrape
Scrape a single URL and return main content as markdown. Uses Playwright (JS rendering) + Trafilatura (content extraction).
- url (str, required): Target URL
- wait_for (int, optional): Wait ms after load for dynamic content, default 2000
