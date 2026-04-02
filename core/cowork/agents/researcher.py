"""Researcher agent implementation."""

from __future__ import annotations

from typing import Any, Dict

from core.cowork.agent_base import Agent, AgentContext, AgentInput, ExecutionPlan, IntentAnalysis, VerificationResult
from core.cowork.agents.factory import register_agent

TASK_AMBIGUITY_LENGTH_THRESHOLD = 50
HIGH_CONFIDENCE_TASK_LENGTH = 20
HIGH_CONFIDENCE_SCORE = 0.8
DEFAULT_CONFIDENCE_SCORE = 0.6
SEARCH_RESULT_LIMIT = 10
CRAWL_SOURCE_LIMIT = 5
MIN_CRAWLED_SOURCES = 3
EXPECTED_CRAWLED_SOURCES = 5
MIN_AVERAGE_CONTENT_LENGTH = 500
HAS_CRAWLED_QUALITY_SCORE = 0.7
NO_CRAWLED_QUALITY_SCORE = 0.0


@register_agent("researcher")
class ResearcherAgent(Agent):
    DEFAULT_ROLE = """You are a Researcher Agent. Your job is to deeply understand research needs before gathering information.

    You excel at:
    - Understanding the true depth of research needed
    - Identifying what sources would be most credible
    - Planning comprehensive but efficient research strategies
    - Recognizing when you have sufficient information

    Remember: Quality research starts with understanding the question deeply."""

    async def _analyze_intent(self, input_data: AgentInput) -> IntentAnalysis:
        task = input_data.task
        return IntentAnalysis(
            user_intent=f"Research about: {task}",
            implicit_needs=[
                "Find authoritative sources",
                "Extract relevant details",
                "Verify information quality",
            ],
            success_criteria=[
                "Comprehensive coverage of topic",
                "Authoritative sources used",
                "Clear summary of findings",
            ],
            constraints=["Time/depth limits", "Source credibility requirements"],
            ambiguity_flags=["How deep should research go?" if len(task) < TASK_AMBIGUITY_LENGTH_THRESHOLD else ""],
            confidence=HIGH_CONFIDENCE_SCORE if len(task) > HIGH_CONFIDENCE_TASK_LENGTH else DEFAULT_CONFIDENCE_SCORE,
        )

    async def _create_plan(self, intent: IntentAnalysis, input_data: AgentInput) -> ExecutionPlan:
        return ExecutionPlan(
            approach="Multi-source research with quality filtering",
            steps=[
                {"action": "search", "description": "Find relevant sources"},
                {"action": "crawl", "description": "Extract content from top sources"},
                {"action": "synthesize", "description": "Combine findings into coherent summary"},
            ],
            required_skills=["search", "crawl", "read_file"],
            expected_output_format="Structured research report with sources",
            fallback_plan="Use fewer but higher-quality sources",
            estimated_complexity="medium",
        )

    async def _execute_plan(self, plan: ExecutionPlan, context: AgentContext, input_data: AgentInput) -> Dict[str, Any]:
        from core.cowork.skills_registry import registry

        search_skill = registry.get("search")
        if search_skill:
            search_result = await search_skill.execute(query=input_data.task, num=SEARCH_RESULT_LIMIT)
            sources = search_result.get("sources", [])
        else:
            sources = []

        crawled = []
        crawl_skill = registry.get("crawl")
        if crawl_skill:
            for source in sources[:CRAWL_SOURCE_LIMIT]:
                url = source.get("url") or source.get("link")
                if url:
                    result = await crawl_skill.execute(url=url)
                    if result.get("success"):
                        crawled.append({"url": url, "content": result.get("content", "")})

        return {
            "sources_found": len(sources),
            "sources_crawled": len(crawled),
            "crawled_data": crawled,
            "query": input_data.task,
        }

    async def _verify_result(self, result: Dict[str, Any], intent: IntentAnalysis, input_data: AgentInput) -> VerificationResult:
        crawled = result.get("crawled_data", [])
        gaps = []
        if len(crawled) < MIN_CRAWLED_SOURCES:
            gaps.append("Insufficient sources crawled")

        improvements = []
        if crawled:
            avg_content_length = sum(len(c.get("content", "")) for c in crawled) / len(crawled)
            if avg_content_length < MIN_AVERAGE_CONTENT_LENGTH:
                improvements.append("Deeper content extraction needed")

        return VerificationResult(
            satisfies_intent=len(crawled) >= MIN_CRAWLED_SOURCES,
            completeness_score=min(len(crawled) / EXPECTED_CRAWLED_SOURCES, 1.0),
            quality_score=HAS_CRAWLED_QUALITY_SCORE if crawled else NO_CRAWLED_QUALITY_SCORE,
            gaps=gaps,
            improvements=improvements,
            needs_iteration=bool(gaps),
        )
