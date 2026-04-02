"""Agent contracts and shared execution primitives.

This module defines the minimal shared agent contract only. Concrete agents
and construction live in ``core.cowork.agents``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional


class AgentStatus(Enum):
    """Agent execution status."""

    IDLE = "idle"
    THINKING = "thinking"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IntentAnalysis:
    """Result of intent analysis phase."""

    user_intent: str
    implicit_needs: List[str]
    success_criteria: List[str]
    constraints: List[str]
    ambiguity_flags: List[str]
    confidence: float


@dataclass
class ExecutionPlan:
    """Result of planning phase."""

    approach: str
    steps: List[Dict[str, Any]]
    required_skills: List[str]
    expected_output_format: str
    fallback_plan: Optional[str]
    estimated_complexity: str


@dataclass
class VerificationResult:
    """Result of verification phase."""

    satisfies_intent: bool
    completeness_score: float
    quality_score: float
    gaps: List[str]
    improvements: List[str]
    needs_iteration: bool


ProgressCallback = Callable[[Dict[str, Any]], Awaitable[None]]


@dataclass
class AgentContext:
    """Standard context passed to all agents."""

    instance_id: str
    workflow_id: str
    session_id: str
    step_id: str
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    previous_outputs: Dict[str, Any] = field(default_factory=dict)
    global_context: Dict[str, Any] = field(default_factory=dict)
    progress_callback: Optional[ProgressCallback] = None

    def add_to_history(self, role: str, content: str) -> None:
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def report_progress(self, phase: str, status: str, details: Dict[str, Any]) -> None:
        if self.progress_callback:
            await self.progress_callback({
                "step_id": self.step_id,
                "phase": phase,
                "status": status,
                "details": details,
                "timestamp": datetime.utcnow().isoformat(),
            })


@dataclass
class AgentInput:
    """Standard input format for all agents."""

    task: str
    data: Dict[str, Any] = field(default_factory=dict)
    context: str = ""
    available_skills: List[str] = field(default_factory=list)


@dataclass
class AgentOutput:
    """Standard output format with full reasoning chain."""

    status: AgentStatus
    result: Dict[str, Any] = field(default_factory=dict)
    intent_analysis: Optional[IntentAnalysis] = None
    execution_plan: Optional[ExecutionPlan] = None
    verification_result: Optional[VerificationResult] = None
    error: Optional[str] = None
    next_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


RESULT_PREVIEW_MAX_CHARS = 200


class Agent(ABC):
    """Base class for thinking-first agents."""

    def __init__(self, agent_id: str, role_description: str, skills: List[str]):
        self.agent_id = agent_id
        self.role_description = role_description
        self.skills = skills
        self.status = AgentStatus.IDLE
        self._thinking_log: List[Dict[str, Any]] = []

    async def execute(self, context: AgentContext, input_data: AgentInput) -> AgentOutput:
        try:
            self.status = AgentStatus.THINKING
            await context.report_progress("thinking", "started", {"message": "Analyzing intent..."})
            intent = await self._analyze_intent(input_data)
            self._thinking_log.append({"phase": "intent", "result": intent})
            await context.report_progress("thinking", "completed", {
                "user_intent": intent.user_intent,
                "confidence": intent.confidence,
            })

            self.status = AgentStatus.PLANNING
            await context.report_progress("planning", "started", {"message": "Creating execution plan..."})
            plan = await self._create_plan(intent, input_data)
            self._thinking_log.append({"phase": "plan", "result": plan})
            await context.report_progress("planning", "completed", {
                "approach": plan.approach,
                "steps_count": len(plan.steps),
            })

            self.status = AgentStatus.EXECUTING
            await context.report_progress("executing", "started", {"message": "Executing plan..."})
            result = await self._execute_plan(plan, context, input_data)
            await context.report_progress("executing", "completed", {"result_preview": str(result)[:RESULT_PREVIEW_MAX_CHARS]})

            self.status = AgentStatus.VERIFYING
            await context.report_progress("verifying", "started", {"message": "Verifying results..."})
            verification = await self._verify_result(result, intent, input_data)
            self._thinking_log.append({"phase": "verify", "result": verification})
            await context.report_progress("verifying", "completed", {
                "satisfies_intent": verification.satisfies_intent,
                "quality_score": verification.quality_score,
            })

            if verification.needs_iteration and verification.improvements:
                await context.report_progress("iteration", "started", {"message": "Refining based on verification..."})
                refined_plan = await self._refine_plan(plan, verification)
                result = await self._execute_plan(refined_plan, context, input_data)
                verification = await self._verify_result(result, intent, input_data)
                await context.report_progress("iteration", "completed", {"message": "Iteration completed"})

            self.status = AgentStatus.COMPLETED
            await context.report_progress("completed", "success", {"message": "Task completed successfully"})
            return AgentOutput(
                status=AgentStatus.COMPLETED,
                result=result,
                intent_analysis=intent,
                execution_plan=plan,
                verification_result=verification,
                metadata={"thinking_log": self._thinking_log},
            )
        except Exception as e:
            self.status = AgentStatus.FAILED
            await context.report_progress("failed", "error", {"error": str(e)})
            return AgentOutput(
                status=AgentStatus.FAILED,
                error=str(e),
                metadata={"thinking_log": self._thinking_log},
            )

    @abstractmethod
    async def _analyze_intent(self, input_data: AgentInput) -> IntentAnalysis:
        pass

    @abstractmethod
    async def _create_plan(self, intent: IntentAnalysis, input_data: AgentInput) -> ExecutionPlan:
        pass

    @abstractmethod
    async def _execute_plan(
        self,
        plan: ExecutionPlan,
        context: AgentContext,
        input_data: AgentInput,
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _verify_result(
        self,
        result: Dict[str, Any],
        intent: IntentAnalysis,
        input_data: AgentInput,
    ) -> VerificationResult:
        pass

    async def _refine_plan(self, original_plan: ExecutionPlan, verification: VerificationResult) -> ExecutionPlan:
        refined_steps = original_plan.steps.copy()
        for improvement in verification.improvements[:3]:
            refined_steps.append({
                "action": "address_gap",
                "description": improvement,
                "priority": "high",
            })

        return ExecutionPlan(
            approach=f"{original_plan.approach} (refined)",
            steps=refined_steps,
            required_skills=original_plan.required_skills,
            expected_output_format=original_plan.expected_output_format,
            fallback_plan=original_plan.fallback_plan,
            estimated_complexity=original_plan.estimated_complexity,
        )

    def get_thinking_prompt(self, phase: str) -> str:
        prompts = {
            "intent": f"""{self.role_description}

## Phase: Intent Analysis
Before doing anything, deeply analyze what the user REALLY wants:

1. **Surface Request**: What did they explicitly ask for?
2. **True Intent**: What do they actually need?
3. **Implicit Needs**: What are they not saying but probably want?
4. **Success Criteria**: How would they know this is done well?
5. **Constraints**: What limitations or boundaries exist?
6. **Ambiguities**: What needs clarification?

Output your analysis in structured format.""",
            "plan": f"""{self.role_description}

## Phase: Solution Planning
Based on the intent analysis, design the optimal solution:

1. **Approach Strategy**: What's the high-level plan?
2. **Detailed Steps**: Break down into actionable steps
3. **Skill Selection**: Which skills from {self.skills} are needed?
4. **Output Format**: What should the final result look like?
5. **Fallback Plan**: What if the primary approach fails?
6. **Complexity**: Is this low/medium/high complexity?

Consider: elegance, efficiency, and completeness.""",
            "verify": f"""{self.role_description}

## Phase: Result Verification
Critically evaluate if the result truly satisfies the original intent:

1. **Intent Match**: Does it address what they really wanted?
2. **Completeness**: Are there gaps or missing pieces?
3. **Quality**: Is the output high quality and professional?
4. **Improvements**: What could make it better?
5. **Iteration Needed**: Should we refine and re-execute?

Be honest and critical. Better to iterate than deliver subpar results.""",
        }
        return prompts.get(phase, "")
