"""Analyst agent implementation."""

from __future__ import annotations

from typing import Any, Dict

from core.cowork.agent_base import Agent, AgentContext, AgentInput, ExecutionPlan, IntentAnalysis, VerificationResult
from core.cowork.agents.factory import register_agent


@register_agent("analyst")
class AnalystAgent(Agent):
    DEFAULT_ROLE = """You are an Analyst Agent. Your job is to deeply understand data before drawing conclusions.

    You excel at:
    - Understanding what insights are truly valuable
    - Choosing the right analytical approach
    - Identifying patterns that others miss
    - Providing actionable recommendations

    Remember: Good analysis starts with asking the right questions."""

    async def _analyze_intent(self, input_data: AgentInput) -> IntentAnalysis:
        return IntentAnalysis(
            user_intent="Analyze provided data for insights",
            implicit_needs=["Identify key patterns", "Filter noise from signal", "Provide actionable insights"],
            success_criteria=["Clear patterns identified", "Noise filtered out", "Structured output"],
            constraints=["Data quality limitations"],
            ambiguity_flags=[],
            confidence=0.7,
        )

    async def _create_plan(self, intent: IntentAnalysis, input_data: AgentInput) -> ExecutionPlan:
        return ExecutionPlan(
            approach="Pattern recognition and insight extraction",
            steps=[
                {"action": "explore", "description": "Understand data structure"},
                {"action": "analyze", "description": "Identify patterns and trends"},
                {"action": "synthesize", "description": "Form actionable insights"},
            ],
            required_skills=["analyze", "filter", "summarize"],
            expected_output_format="Structured analysis with key insights",
            fallback_plan="Focus on most obvious patterns",
            estimated_complexity="medium",
        )

    async def _execute_plan(self, plan: ExecutionPlan, context: AgentContext, input_data: AgentInput) -> Dict[str, Any]:
        data = input_data.data
        return {
            "raw_data_summary": f"Analyzed {len(data)} data items",
            "insights": ["Data structure analyzed"],
            "recommendations": [],
        }

    async def _verify_result(self, result: Dict[str, Any], intent: IntentAnalysis, input_data: AgentInput) -> VerificationResult:
        insights = result.get("insights", [])
        return VerificationResult(
            satisfies_intent=len(insights) > 0,
            completeness_score=0.6,
            quality_score=0.7,
            gaps=["Deeper analysis needed"] if len(insights) < 3 else [],
            improvements=["More specific recommendations"],
            needs_iteration=len(insights) < 3,
        )
