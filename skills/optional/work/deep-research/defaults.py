"""Deep-research skill-local defaults (co-located for a self-contained skill tree).

Environment:
    SOPHON_DEEP_RESEARCH_URLS: Overrides ``urls_per_sub_question`` (int).
    SOPHON_DEEP_RESEARCH_CRAWLER_CONCURRENCY: Overrides ``crawler_concurrency`` (int).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DeepResearchConfig:
    """Limits for the optional deep-research skill pipeline.

    Attributes:
        urls_per_sub_question (int): Max URLs fetched per sub-question.
        crawler_concurrency (int): Concurrent crawler tasks cap.
    """

    urls_per_sub_question: int = 10
    crawler_concurrency: int = 3


def resolve_deep_research_config() -> DeepResearchConfig:
    """Load deep-research limits from environment variables.

    Returns:
        Frozen ``DeepResearchConfig`` with parsed ints or built-in defaults.
    """
    return DeepResearchConfig(
        urls_per_sub_question=int(os.getenv("SOPHON_DEEP_RESEARCH_URLS", "10")),
        crawler_concurrency=int(os.getenv("SOPHON_DEEP_RESEARCH_CRAWLER_CONCURRENCY", "3")),
    )
