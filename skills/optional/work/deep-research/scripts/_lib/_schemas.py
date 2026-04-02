"""Dataclasses for deep-research notes and per-URL source rows."""

from dataclasses import dataclass, field

from deep_research_constants import DEEP_RESEARCH_SOURCE_TEXT_PREVIEW_MAX_CHARS


@dataclass
class Source:
    """One crawled or search result row.

    Attributes:
        url (str): Canonical link.
        title (str): Page or hit title.
        snippet (str): Short summary from search or empty after fetch.
        full_text (str): Extracted body text (may be truncated in ``as_context``).
    """

    url: str
    title: str
    snippet: str
    full_text: str = ""


@dataclass
class ResearchNote:
    """Material gathered for a single sub-question.

    Attributes:
        sub_question (str): Planner sub-question text.
        sources (list[Source]): URLs and text collected for this branch.
    """

    sub_question: str
    sources: list[Source] = field(default_factory=list)

    def as_context(self) -> str:
        """Format this note as an LLM context block (truncated full_text).

        Returns:
            str: Markdown-ish block listing sub-question and sources.
        """
        lines = [f"### Sub-question: {self.sub_question}"]
        for i, src in enumerate(self.sources, 1):
            lines.append(f"\n**Source {i}**: {src.title or src.url}")
            lines.append(f"URL: {src.url}")
            if src.snippet:
                lines.append(f"Snippet: {src.snippet}")
            if src.full_text:
                lines.append(f"Content: {src.full_text[:DEEP_RESEARCH_SOURCE_TEXT_PREVIEW_MAX_CHARS]}")
        return "\n".join(lines)

    def all_urls(self) -> list[str]:
        """Return non-empty source URLs in order.

        Returns:
            list[str]: URLs from ``sources``.
        """
        return [s.url for s in self.sources if s.url]
