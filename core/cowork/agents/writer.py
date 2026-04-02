"""Writer agent implementation."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from core.cowork.agent_base import Agent, AgentContext, AgentInput, ExecutionPlan, IntentAnalysis, VerificationResult
from core.cowork.agents.factory import register_agent

INTENT_CONFIDENCE_SCORE = 0.8
REPORT_PREVIEW_CHARS = 1000
MIN_REPORT_BRIEF_CHARS = 500
MIN_REPORT_SATISFIES_CHARS = 200
DETAILED_REPORT_CHARS = 1000
QUALITY_SCORE_HIGH = 0.8
QUALITY_SCORE_LOW = 0.6


@register_agent("writer")
class WriterAgent(Agent):
    DEFAULT_ROLE = """You are a Writer Agent. Your job is to deeply understand communication goals before writing.

    You excel at:
    - Understanding audience and purpose
    - Choosing the right structure and tone
    - Creating clear, compelling content
    - Ensuring completeness and accuracy

    Remember: Good writing starts with understanding why you're writing."""

    async def _analyze_intent(self, input_data: AgentInput) -> IntentAnalysis:
        return IntentAnalysis(
            user_intent="Create structured output/report",
            implicit_needs=["Clear communication", "Professional quality", "Appropriate format"],
            success_criteria=["Clear and readable", "Complete coverage", "Professional tone"],
            constraints=["Format requirements"],
            ambiguity_flags=[],
            confidence=INTENT_CONFIDENCE_SCORE,
        )

    async def _create_plan(self, intent: IntentAnalysis, input_data: AgentInput) -> ExecutionPlan:
        return ExecutionPlan(
            approach="Structured report generation",
            steps=[
                {"action": "outline", "description": "Create document structure"},
                {"action": "draft", "description": "Write content sections"},
                {"action": "polish", "description": "Refine and format output"},
            ],
            required_skills=["generate_report", "format_output"],
            expected_output_format="Markdown report with clear sections",
            fallback_plan="Simpler format with key points only",
            estimated_complexity="medium",
        )

    async def _execute_plan(self, plan: ExecutionPlan, context: AgentContext, input_data: AgentInput) -> Dict[str, Any]:
        data = input_data.data
        report_lines = [
            "# Report",
            "",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Summary",
            "",
            json.dumps(data, indent=2)[:REPORT_PREVIEW_CHARS],
            "",
            "## Details",
            "",
            "Based on the provided data.",
        ]
        return {"report": "\n".join(report_lines), "format": "markdown"}

    async def _verify_result(self, result: Dict[str, Any], intent: IntentAnalysis, input_data: AgentInput) -> VerificationResult:
        report = result.get("report", "")
        gaps = []
        if len(report) < MIN_REPORT_BRIEF_CHARS:
            gaps.append("Report too brief")
        return VerificationResult(
            satisfies_intent=len(report) > MIN_REPORT_SATISFIES_CHARS,
            completeness_score=min(len(report) / DETAILED_REPORT_CHARS, 1.0),
            quality_score=QUALITY_SCORE_HIGH if len(report) > MIN_REPORT_BRIEF_CHARS else QUALITY_SCORE_LOW,
            gaps=gaps,
            improvements=["More detailed sections"] if len(report) < DETAILED_REPORT_CHARS else [],
            needs_iteration=len(gaps) > 0,
        )
