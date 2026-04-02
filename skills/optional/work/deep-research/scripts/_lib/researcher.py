"""Execute the research stage: search, URL filtering/selection, parallel crawl.

Produces one ``ResearchNote`` per ``SubQuestion``. Uses ``_prompts``, ``_schemas``, and ``_urls``.
"""

from __future__ import annotations

import asyncio
import logging
from _schemas import ResearchNote, Source
from _urls import llm_denoise_urls, llm_select_urls, parse_search_results
from planner import SubQuestion

logger = logging.getLogger(__name__)


async def _fetch_via_crawler(
    url: str,
    execute_tool,
    wait_for: int = 3000,
) -> tuple[str, str]:
    """Fetch one URL via the ``crawler.scrape`` tool.

    Args:
        url (str): Target page.
        execute_tool: Async callable used to invoke nested skills.
        wait_for (int): Playwright wait ms passed to the crawler.

    Returns:
        tuple[str, str]: ``(url, content)`` on success; ``("", "")`` on error or empty result.
    """
    try:
        result = await execute_tool("crawler", "scrape", {"url": url, "wait_for": wait_for})
        if result.get("error"):
            return "", ""
        content = result.get("result", "")
        return url, content
    except Exception as e:
        logger.debug("crawler.scrape failed url=%s: %s", url, e)
        return "", ""


async def _research_sub_question(
    sub_question: SubQuestion,
    execute_tool,
    provider,
    urls_per_sub: int,
    crawler_concurrency: int,
) -> ResearchNote:
    """
    Search for each query, LLM denoise URLs, LLM select top URLs, fetch via crawler in parallel.
    """
    all_items: list[dict] = []
    seen_urls: set[str] = set()

    for query in sub_question.queries:
        try:
            result = await execute_tool("search", "search", {"query": query, "num": 10})
            items = parse_search_results(result)
            for item in items:
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_items.append(item)
        except Exception as e:
            logger.warning("search failed query=%r: %s", query, e)

    if not all_items:
        return ResearchNote(sub_question=sub_question.question)

    denoised_items = await llm_denoise_urls(sub_question.question, all_items, provider)
    if not denoised_items:
        return ResearchNote(sub_question=sub_question.question)

    selected_urls = await llm_select_urls(
        sub_question.question, denoised_items, provider, urls_per_sub
    )
    url_to_item = {item["url"]: item for item in denoised_items}

    semaphore = asyncio.Semaphore(crawler_concurrency)

    async def bounded_fetch(url: str) -> tuple[str, str, str, str]:
        async with semaphore:
            _, full_text = await _fetch_via_crawler(url, execute_tool)
        item = url_to_item.get(url, {})
        return url, item.get("title", url), item.get("snippet", ""), full_text

    tasks = [bounded_fetch(url) for url in selected_urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    sources: list[Source] = []
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            url = selected_urls[i] if i < len(selected_urls) else ""
            item = url_to_item.get(url, {})
            sources.append(Source(
                url=url,
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                full_text="",
            ))
        else:
            url, title, snippet, full_text = res
            sources.append(Source(url=url, title=title, snippet=snippet, full_text=full_text))

    # Drop sources with no meaningful content to reduce noise in References
    sources = [s for s in sources if s.full_text and len(s.full_text.strip()) > 150]
    return ResearchNote(sub_question=sub_question.question, sources=sources)


async def research_parallel(
    sub_questions: list[SubQuestion],
    execute_tool,
    provider,
    urls_per_sub_question: int = 10,
    crawler_concurrency: int = 3,
) -> list[ResearchNote]:
    """
    Research all sub-questions in parallel.
    Each sub-question: search → LLM denoise URLs → LLM select top URLs → crawler fetch (with concurrency limit).
    """
    tasks = [
        _research_sub_question(sq, execute_tool, provider, urls_per_sub_question, crawler_concurrency)
        for sq in sub_questions
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    notes: list[ResearchNote] = []
    for sq, result in zip(sub_questions, results):
        if isinstance(result, Exception):
            logger.warning("sub_question=%r failed: %s", sq.question, result)
            notes.append(ResearchNote(sub_question=sq.question))
        else:
            notes.append(result)
    return notes
