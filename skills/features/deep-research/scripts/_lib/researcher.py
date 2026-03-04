"""
Researcher - For each sub-question: search + LLM denoise URLs + LLM select top URLs + crawler fetch in parallel.

Produces a list of ResearchNote, one per sub-question.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field

from planner import SubQuestion

logger = logging.getLogger(__name__)

_DENOISE_SYSTEM = (
    "You are a research assistant. The user asked a research question. Below are search results (title, URL, snippet). "
    "Your task: filter out irrelevant entries. "
    "KEEP only URLs that may help answer the research question. "
    "REMOVE off-topic, spam, adult content, unrelated ads, or clearly wrong matches—judge by title and snippet. "
    "Reply with JSON only: {\"urls\": [\"url1\", \"url2\", ...]}. Use exact URLs from the list. "
    "Return only those to keep. If all are noise, return {\"urls\": []}."
)

_URL_SELECT_SYSTEM = (
    "You are a research assistant. Given search results for a sub-question, "
    "select ONLY URLs that DIRECTLY discuss the topic. STRICTLY EXCLUDE irrelevant results: "
    "reviews (e.g. B1 review, amenities review), services (chiropractic, real estate), "
    "library catalogs, help centers, generic templates. Prefer authoritative sources (news, reports). "
    "Reply with JSON only: {\"urls\": [\"url1\", \"url2\", ...]}\n"
    "Return up to {n} URLs in order of relevance. Use exact URLs from the list. "
    "If few results are relevant, return fewer—never include irrelevant URLs."
)


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


async def _llm_denoise_urls(
    sub_question: str,
    items: list[dict],
    provider,
) -> list[dict]:
    """LLM filters URLs by relevance to the research question. No hardcoded patterns."""
    if not items:
        return []
    prompt_lines = [
        f"Research question: {sub_question}",
        "",
        "Search results (filter to keep only relevant ones):",
    ]
    for i, item in enumerate(items, 1):
        title = item.get("title", "")
        url = item.get("url", "")
        snippet = item.get("snippet", "")
        prompt_lines.append(f"{i}. {title}\n   {url}\n   {snippet}")
    prompt = "\n".join(prompt_lines)
    try:
        resp = await provider.chat(
            [{"role": "user", "content": prompt}],
            tools=None,
            system_prompt=_DENOISE_SYSTEM,
        )
        content = (resp.get("content") or "").strip()
        if "```" in content:
            for part in content.split("```"):
                if "urls" in part:
                    content = part.replace("json", "").strip()
                    break
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(content[start:end])
            urls = data.get("urls", [])
            if isinstance(urls, list):
                valid = {item["url"] for item in items}
                keep_urls = {u for u in urls if isinstance(u, str) and u in valid}
                return [item for item in items if item.get("url") in keep_urls]
    except Exception as e:
        logger.warning("_llm_denoise_urls failed: %s", e)
    return items


def _parse_search_results(result: dict) -> list[dict]:
    """Extract list of {title, url, snippet} from search skill output."""
    sources = result.get("sources")
    if sources:
        return [
            {"title": s.get("title", ""), "url": s.get("url", ""), "snippet": ""}
            for s in sources
            if s.get("url", "").startswith("http")
        ]
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


async def _llm_select_urls(
    sub_question: str,
    all_items: list[dict],
    provider,
    n: int,
) -> list[str]:
    """LLM selects top n most relevant URLs from search results."""
    if len(all_items) <= n:
        return [item["url"] for item in all_items if item.get("url")]
    prompt_lines = [
        f"Sub-question: {sub_question}",
        "",
        "Search results:",
    ]
    for i, item in enumerate(all_items, 1):
        url = item.get("url", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        prompt_lines.append(f"{i}. {title}\n   {url}\n   {snippet}")
    prompt = "\n".join(prompt_lines)
    try:
        resp = await provider.chat(
            [{"role": "user", "content": prompt}],
            tools=None,
            system_prompt=_URL_SELECT_SYSTEM.format(n=n),
        )
        content = (resp.get("content") or "").strip()
        if "```" in content:
            for part in content.split("```"):
                if "urls" in part:
                    content = part.replace("json", "").strip()
                    break
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(content[start:end])
            urls = data.get("urls", [])
            if isinstance(urls, list):
                valid = {item["url"] for item in all_items}
                return [u for u in urls if isinstance(u, str) and u in valid][:n]
    except Exception as e:
        logger.warning("_llm_select_urls failed: %s", e)
    return [item["url"] for item in all_items[:n] if item.get("url")]


async def _fetch_via_crawler(
    url: str,
    execute_tool,
    wait_for: int = 3000,
) -> tuple[str, str]:
    """Fetch URL via crawler.scrape. Returns (title_or_url, full_text). On error returns ('', '')."""
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

    denoised_items = await _llm_denoise_urls(sub_question.question, all_items, provider)
    if not denoised_items:
        return ResearchNote(sub_question=sub_question.question)

    selected_urls = await _llm_select_urls(
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
