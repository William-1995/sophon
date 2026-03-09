"""
Deep Research - URL parsing, filtering, and selection.

Extracts URLs from search results; LLM denoises and selects top-N by relevance.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from _prompts import DENOISE_SYSTEM, URL_SELECT_SYSTEM_TEMPLATE

logger = logging.getLogger(__name__)


def parse_search_results(result: dict) -> list[dict]:
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


def _extract_urls_from_llm_response(content: str, valid_urls: set[str]) -> list[str] | None:
    """Parse JSON urls array from LLM response. Returns list or None on failure."""
    content = (content or "").strip()
    if "```" in content:
        for part in content.split("```"):
            if "urls" in part:
                content = part.replace("json", "").strip()
                break
    start = content.find("{")
    end = content.rfind("}") + 1
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(content[start:end])
        urls = data.get("urls", [])
        if not isinstance(urls, list):
            return None
        return [u for u in urls if isinstance(u, str) and u in valid_urls]
    except json.JSONDecodeError:
        return None


async def llm_denoise_urls(
    sub_question: str,
    items: list[dict],
    provider: Any,
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
            system_prompt=DENOISE_SYSTEM,
        )
        content = (resp.get("content") or "").strip()
        valid = {item["url"] for item in items}
        extracted = _extract_urls_from_llm_response(content, valid)
        if extracted is not None:
            keep_urls = set(extracted)
            return [item for item in items if item.get("url") in keep_urls]
    except Exception as e:
        logger.warning("llm_denoise_urls failed: %s", e)
    return items


async def llm_select_urls(
    sub_question: str,
    all_items: list[dict],
    provider: Any,
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
            system_prompt=URL_SELECT_SYSTEM_TEMPLATE.format(n=n),
        )
        content = (resp.get("content") or "").strip()
        valid = {item["url"] for item in all_items}
        extracted = _extract_urls_from_llm_response(content, valid)
        if extracted is not None:
            return extracted[:n]
    except Exception as e:
        logger.warning("llm_select_urls failed: %s", e)
    return [item["url"] for item in all_items[:n] if item.get("url")]
