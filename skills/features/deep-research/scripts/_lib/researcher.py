"""
Researcher - For each sub-question: search + fetch top URLs in parallel.

Produces a list of ResearchNote, one per sub-question.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from fetch import fetch_pages, FetchedPage
from planner import SubQuestion

logger = logging.getLogger(__name__)

FETCH_TOP_N_URLS = 3


@dataclass
class Source:
    url: str
    title: str
    snippet: str
    full_text: str = ""


@dataclass
class ResearchNote:
    sub_question: str
    sources: list[Source] = field(default_factory=list)

    def as_context(self) -> str:
        """Format note as LLM-readable context block."""
        lines = [f"### Sub-question: {self.sub_question}"]
        for i, src in enumerate(self.sources, 1):
            lines.append(f"\n**Source {i}**: {src.title or src.url}")
            lines.append(f"URL: {src.url}")
            if src.snippet:
                lines.append(f"Snippet: {src.snippet}")
            if src.full_text:
                lines.append(f"Content: {src.full_text[:800]}")
        return "\n".join(lines)

    def all_urls(self) -> list[str]:
        return [s.url for s in self.sources if s.url]


def _parse_search_results(result: dict) -> list[dict]:
    """Extract list of {title, url, snippet} from search skill output."""
    raw = result.get("result", "")
    if not raw:
        return []
    items: list[dict] = []
    blocks = raw.strip().split("\n\n")
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue
        title = lines[0].split(". ", 1)[-1].strip() if ". " in lines[0] else lines[0].strip()
        url = lines[1].strip() if len(lines) > 1 else ""
        snippet = lines[2].strip() if len(lines) > 2 else ""
        if url.startswith("http"):
            items.append({"title": title, "url": url, "snippet": snippet})
    return items


async def _research_sub_question(
    sub_question: SubQuestion,
    execute_tool,
) -> ResearchNote:
    """
    Search for each query, collect URLs, fetch top-N pages in parallel (fork/join).
    """
    all_items: list[dict] = []
    seen_urls: set[str] = set()

    for query in sub_question.queries:
        try:
            result = await execute_tool("search", "search", {"query": query, "num": 5})
            items = _parse_search_results(result)
            for item in items:
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_items.append(item)
        except Exception as e:
            logger.warning("search failed query=%r: %s", query, e)

    if not all_items:
        return ResearchNote(sub_question=sub_question.question)

    top_items = all_items[:FETCH_TOP_N_URLS]
    remaining_items = all_items[FETCH_TOP_N_URLS:]

    # Fork/join: fetch top-N URLs in parallel
    top_urls = [item["url"] for item in top_items]
    fetched_pages: list[FetchedPage] = await fetch_pages(top_urls)
    url_to_page = {p.url: p for p in fetched_pages}

    sources: list[Source] = []
    for item in top_items:
        url = item["url"]
        page = url_to_page.get(url)
        sources.append(Source(
            url=url,
            title=page.title if page and page.ok and page.title else item.get("title", ""),
            snippet=item.get("snippet", ""),
            full_text=page.text if page and page.ok else "",
        ))
    # Include remaining search-only results for breadth (no fetch)
    for item in remaining_items:
        sources.append(Source(
            url=item["url"],
            title=item.get("title", ""),
            snippet=item.get("snippet", ""),
        ))

    return ResearchNote(sub_question=sub_question.question, sources=sources)


async def research_parallel(
    sub_questions: list[SubQuestion],
    execute_tool,
) -> list[ResearchNote]:
    """
    Research all sub-questions in parallel (fork/join at sub-question level).
    Each sub-question internally does serial search + parallel URL fetch.
    """
    tasks = [_research_sub_question(sq, execute_tool) for sq in sub_questions]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    notes: list[ResearchNote] = []
    for sq, result in zip(sub_questions, results):
        if isinstance(result, Exception):
            logger.warning("sub_question=%r failed: %s", sq.question, result)
            notes.append(ResearchNote(sub_question=sq.question))
        else:
            notes.append(result)
    return notes
