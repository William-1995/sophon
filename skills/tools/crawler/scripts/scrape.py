#!/usr/bin/env python3
"""Scrape a single URL via Playwright. No MCP, no API key.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sys
from constants import CRAWLER_DEFAULT_WAIT_FOR_MS, PROGRESS_URL_DISPLAY_MAX_CHARS


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    url = (args.get("url") or "").strip()
    if not url:
        print(json.dumps({"error": "url is required"}))
        return
    wait_ms = int(args.get("wait_for", CRAWLER_DEFAULT_WAIT_FOR_MS))
    try:
        from core.ipc import get_reporter
        r = get_reporter()
        if r:
            r.emit(
                "progress",
                {
                    "phase": "crawl",
                    "url": url[:PROGRESS_URL_DISPLAY_MAX_CHARS],
                    "display_text": f"Crawling: {url[:PROGRESS_URL_DISPLAY_MAX_CHARS]}",
                },
            )
    except Exception:
        pass
    try:
        from playwright.sync_api import sync_playwright
        import trafilatura
    except ImportError as e:
        print(json.dumps({
            "error": f"Missing dependency: {e}. Run: pip install playwright trafilatura && playwright install chromium"
        }))
        return

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if wait_ms > 0:
                    page.wait_for_timeout(wait_ms)
                html = page.content()
            finally:
                browser.close()

        content = trafilatura.extract(html, output_format="markdown", url=url)
        if not content:
            content = trafilatura.extract(html, output_format="txt") or "(No extractable content)"
        references = [{"title": "Source", "url": url}]
        print(json.dumps({"result": content, "url": url, "references": references, "observation": content}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main()
