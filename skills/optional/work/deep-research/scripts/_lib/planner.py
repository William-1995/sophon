"""Plan deep research: one LLM call to split a question into sub-questions and search queries."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MIN_SUB_QUESTIONS = 2
MAX_SUB_QUESTIONS = 5
QUERIES_PER_SUB_QUESTION = 2


@dataclass
class SubQuestion:
    """One branch of the research plan.

    Attributes:
        question (str): Focused sub-question text.
        queries (list[str]): Web search strings for this sub-question.
    """

    question: str
    queries: list[str]


@dataclass
class ResearchPlan:
    """Full decomposition returned by the planner LLM.

    Attributes:
        original_question (str): User-facing research ask.
        sub_questions (list[SubQuestion]): Planned branches with queries.
    """

    original_question: str
    sub_questions: list[SubQuestion] = field(default_factory=list)

    def all_queries(self) -> list[tuple[str, str]]:
        """Flatten sub-questions into (sub_question_text, query) pairs.

        Returns:
            list[tuple[str, str]]: Pairs in planner order.
        """
        return [
            (sq.question, q)
            for sq in self.sub_questions
            for q in sq.queries
        ]


_PLAN_SYSTEM = (
    "You are a research planning assistant. "
    "Given a research question, decompose it into focused sub-questions and generate "
    f"{QUERIES_PER_SUB_QUESTION} targeted web search queries per sub-question. "
    f"Use {MIN_SUB_QUESTIONS}–{MAX_SUB_QUESTIONS} sub-questions. "
    "Focus on distinct angles: facts, context, comparisons, recent developments, expert opinions.\n\n"
    "Reply with JSON only:\n"
    "{\n"
    '  "sub_questions": [\n'
    '    {"question": "...", "queries": ["query1", "query2"]},\n'
    '    ...\n'
    "  ]\n"
    "}"
)


def _parse_plan(content: str, original_question: str) -> ResearchPlan:
    """Parse LLM JSON output into ResearchPlan. Fallback to single sub-question on failure."""
    content = (content or "").strip()
    if "```" in content:
        for part in content.split("```"):
            if "sub_questions" in part:
                content = part.replace("json", "").strip()
                break
    try:
        m = re.search(r'\{.*"sub_questions".*\}', content, re.DOTALL)
        if m:
            data = json.loads(m.group())
        else:
            data = json.loads(content)
        sub_questions = [
            SubQuestion(
                question=sq.get("question", ""),
                queries=[q for q in sq.get("queries", []) if q],
            )
            for sq in data.get("sub_questions", [])
            if sq.get("question")
        ]
        if sub_questions:
            return ResearchPlan(
                original_question=original_question,
                sub_questions=sub_questions,
            )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("planner: failed to parse plan json: %s", e)

    return ResearchPlan(
        original_question=original_question,
        sub_questions=[
            SubQuestion(question=original_question, queries=[original_question])
        ],
    )


async def plan_research(question: str, provider) -> ResearchPlan:
    """Call LLM to decompose question into sub-questions and queries."""
    try:
        resp = await provider.chat(
            [{"role": "user", "content": f"Research question: {question}"}],
            tools=None,
            system_prompt=_PLAN_SYSTEM,
        )
        content = (resp.get("content") or "").strip()
        plan = _parse_plan(content, question)
        logger.info(
            "planner: %d sub-questions, %d total queries",
            len(plan.sub_questions),
            sum(len(sq.queries) for sq in plan.sub_questions),
        )
        return plan
    except Exception as e:
        logger.warning("plan_research failed: %s", e)
        return ResearchPlan(
            original_question=question,
            sub_questions=[SubQuestion(question=question, queries=[question])],
        )
