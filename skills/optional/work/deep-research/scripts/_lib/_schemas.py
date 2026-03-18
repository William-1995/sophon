"""
Deep Research - Data schemas for research notes and sources.
"""

from dataclasses import dataclass, field


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
