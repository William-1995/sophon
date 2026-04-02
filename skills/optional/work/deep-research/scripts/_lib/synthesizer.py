"""Synthesize deep-research notes into a report, summary, and source list (one LLM call)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
logger = logging.getLogger(__name__)

MAX_NOTE_CONTEXT_CHARS = 8000

@dataclass
class ResearchResult:
    """Final structured output of the synthesizer.

    Attributes:
        report (str): Long-form markdown-style report.
        summary (str): Short abstract.
        sources (list[dict]): ``{"url", "title"}`` dicts in discovery order.
        sources_count (int): Count of unique sources (may match ``len(sources)``).
    """

    report: str
    summary: str
    sources: list[dict] = field(default_factory=list)  # [{url, title}]
    sources_count: int = 0


def _build_notes_context(notes) -> tuple[str, list[dict]]:
    """Concatenate note context blocks and collect unique source metadata.

    Args:
        notes: Iterable of ``ResearchNote`` instances.

    Returns:
        tuple[str, list[dict]]: ``(context_str, all_sources)`` where ``all_sources`` lists
        each unique URL once in discovery order.
    """
    all_sources: list[dict] = []
    seen_urls: set[str] = set()
    blocks: list[str] = []

    for note in notes:
        block = note.as_context()
        blocks.append(block)
        for src in note.sources:
            if src.url and src.url not in seen_urls:
                seen_urls.add(src.url)
                all_sources.append({"url": src.url, "title": src.title or src.url})

    context = "\n\n---\n\n".join(blocks)
    if len(context) > MAX_NOTE_CONTEXT_CHARS:
        context = context[:MAX_NOTE_CONTEXT_CHARS] + "\n\n[...truncated for context limit...]"

    return context, all_sources


_SYNTHESIS_SYSTEM = (
    "You are a research synthesis expert. "
    "You receive research notes from multiple sub-questions and must produce a structured report.\n\n"
    "Reply with JSON only:\n"
    "{\n"
    '  "summary": "One paragraph executive summary (2-4 sentences)",\n'
    '  "report": "Full markdown report with sections: ## Overview, ## Key Findings, ## Analysis, ## Conclusion"\n'
    "}\n\n"
    "Requirements:\n"
    "- Be factual and cite sources inline using [Source N] notation where N is the source number\n"
    "- Do NOT invent facts; only use what's in the notes\n"
    "- If notes are sparse or conflicting, say so explicitly\n"
    "- report should be 400-800 words in markdown"
)


def _parse_synthesis(content: str) -> tuple[str, str]:
    """Parse LLM JSON output → (summary, report). Returns empty strings on failure."""
    content = (content or "").strip()
    if "```" in content:
        for part in content.split("```"):
            if "summary" in part or "report" in part:
                content = part.replace("json", "").strip()
                break
    try:
        m = re.search(r'\{.*"summary".*"report".*\}', content, re.DOTALL)
        if not m:
            m = re.search(r'\{.*"report".*"summary".*\}', content, re.DOTALL)
        if m:
            data = json.loads(m.group())
            return data.get("summary", ""), data.get("report", "")
        data = json.loads(content)
        return data.get("summary", ""), data.get("report", "")
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("synthesizer: failed to parse json: %s", e)
        return "", content


async def synthesize(
    question: str,
    notes,
    provider,
) -> ResearchResult:
    """LLM-synthesize notes into a structured ResearchResult."""
    notes_context, all_sources = _build_notes_context(notes)
    sources_list = "\n".join(
        f"[Source {i+1}] {s['title']} — {s['url']}"
        for i, s in enumerate(all_sources)
    )
    user_prompt = (
        f"Research question: {question}\n\n"
        f"Sources available:\n{sources_list}\n\n"
        f"Research notes:\n{notes_context}"
    )
    try:
        resp = await provider.chat(
            [{"role": "user", "content": user_prompt}],
            tools=None,
            system_prompt=_SYNTHESIS_SYSTEM,
        )
        content = (resp.get("content") or "").strip()
        summary, report = _parse_synthesis(content)
        if not report:
            report = content
        if not summary and report:
            summary = report.split("\n\n")[0].strip().lstrip("#").strip()
    except Exception as e:
        logger.warning("synthesize failed: %s", e)
        summary = "Research completed."
        report = f"Error during synthesis: {e}"

    return ResearchResult(
        report=report,
        summary=summary,
        sources=all_sources,
        sources_count=len(all_sources),
    )
