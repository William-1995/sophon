"""Fetch HTML and extract readable text for deep-research (internal, not a standalone skill).

Uses ``httpx`` and ``beautifulsoup4``. Intended for import from the deep-research pipeline only.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
import httpx
from deep_research_constants import DEEP_RESEARCH_ERROR_PREVIEW_MAX_CHARS

logger = logging.getLogger(__name__)

FETCH_TIMEOUT_SECONDS = 10
MAX_TEXT_CHARS = 3000
FETCH_CONCURRENCY = 5

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_NOISE_TAGS = {"script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"}


@dataclass
class FetchedPage:
    url: str
    title: str
    text: str
    ok: bool
    error: str = ""


def _extract_text(html: str, max_chars: int = MAX_TEXT_CHARS) -> tuple[str, str]:
    """Extract (title, clean_text) from HTML using BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(list(_NOISE_TAGS)):
            tag.decompose()
        title = (soup.title.string or "").strip() if soup.title else ""
        main = soup.find("article") or soup.find("main") or soup.find("body") or soup
        text = " ".join(main.get_text(separator=" ").split())
        return title, text[:max_chars]
    except Exception as e:
        logger.debug("_extract_text failed: %s", e)
        return "", ""


async def fetch_page(url: str, client: httpx.AsyncClient) -> FetchedPage:
    """Fetch a single URL and return extracted text."""
    try:
        resp = await client.get(url, headers=_HEADERS, follow_redirects=True, timeout=FETCH_TIMEOUT_SECONDS)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return FetchedPage(url=url, title="", text="", ok=False, error=f"unsupported content-type: {content_type}")
        title, text = _extract_text(resp.text)
        if not text:
            return FetchedPage(url=url, title=title, text="", ok=False, error="empty text after extraction")
        return FetchedPage(url=url, title=title, text=text, ok=True)
    except Exception as e:
        err = str(e)[:DEEP_RESEARCH_ERROR_PREVIEW_MAX_CHARS]
        logger.debug("fetch_page failed url=%s: %s", url, err)
        return FetchedPage(url=url, title="", text="", ok=False, error=err)


async def fetch_pages(urls: list[str]) -> list[FetchedPage]:
    """
    Fetch multiple URLs concurrently (fork/join).
    Semaphore limits max concurrent connections.
    """
    semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)

    async def bounded_fetch(url: str, client: httpx.AsyncClient) -> FetchedPage:
        async with semaphore:
            return await fetch_page(url, client)

    async with httpx.AsyncClient() as client:
        tasks = [bounded_fetch(url, client) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    pages: list[FetchedPage] = []
    for url, result in zip(urls, results):
        if isinstance(result, Exception):
            pages.append(
                FetchedPage(
                    url=url,
                    title="",
                    text="",
                    ok=False,
                    error=str(result)[:DEEP_RESEARCH_ERROR_PREVIEW_MAX_CHARS],
                )
            )
        else:
            pages.append(result)
    return pages
