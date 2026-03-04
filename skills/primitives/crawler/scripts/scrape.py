#!/usr/bin/env python3
"""Scrape a single URL via Playwright. No MCP, no API key."""
import json
import sys


def main() -> None:
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    url = (args.get("url") or "").strip()
    if not url:
        print(json.dumps({"error": "url is required"}))
        return
    wait_ms = int(args.get("wait_for", 2000))
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
