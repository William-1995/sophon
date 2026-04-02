"""Iteration controller.

Manages Critic iteration process: execute → critique → (retry → critique) → converge.
"""

from typing import Any, Dict, Optional, Callable
import asyncio

from core.cowork import AgentRuntime, AgentResult
from core.cowork.critic.config import CriticConfig, CritiqueFeedback
from core.cowork.critic.checker import ConvergenceChecker, ConvergenceResult

class IterationController:
    """Iteration controller.
    
    Responsible for managing Agent execution and Critic review iteration loop.
    """
    
    def __init__(
        self,
        runtime: AgentRuntime,
        config: CriticConfig,
    ):
        self.runtime = runtime
        self.config = config
        self.checker = ConvergenceChecker(config)
    
    async def execute_with_critic(
        self,
        agent_id: str,
        task: Dict[str, Any],
        on_iteration: Optional[Callable[[int, AgentResult, ConvergenceResult], None]] = None,
    ) -> AgentResult:
        """Execution with Critic.
        
        Execution flow:
        1. Agent executes → 2. Critic reviews → 3. If not converged, retry → back to 1
        
        Args:
            agent_id: Agent ID
            task: Initial task
            on_iteration: Callback for each iteration
            
        Returns:
            Final result (may be converged or timed out)
        """
        iteration = 0
        current_task = task
        last_result: Optional[AgentResult] = None
        
        while iteration < self.config.max_iterations:
            iteration += 1
            
            # 1. Agent execution
            result = await self.runtime.invoke(agent_id, current_task)
            last_result = result
            
            # 2. Critic review
            convergence = self.checker.check(result, iteration)
            
            # Callback notification
            if on_iteration:
                on_iteration(iteration, result, convergence)
            
            # 3. Check if converged
            if convergence.converged:
                return result
            
            # 4. Not converged, prepare retry
            if iteration < self.config.max_iterations:
                current_task = self._prepare_retry_task(
                    task,
                    convergence.feedback,
                    iteration,
                )
        
        # Reached maximum iterations
        return self._handle_timeout(last_result)
    
    def _prepare_retry_task(
        self,
        original_task: Dict[str, Any],
        feedback: Optional[CritiqueFeedback],
        iteration: int,
    ) -> Dict[str, Any]:
        """Prepare retry task.
        
        Args:
            original_task: Original task
            feedback: Critic feedback
            iteration: Current iteration count
            
        Returns:
            Enhanced task parameters
        """
        retry_task = dict(original_task)
        
        # Add retry context
        retry_task["_retry_context"] = {
            "iteration": iteration,
            "is_retry": True,
        }
        
        if feedback:
            # Add feedback information
            retry_task["_critique"] = {
                "feedback": feedback.feedback,
                "issues": feedback.issues,
                "suggestions": feedback.suggestions,
                "previous_score": feedback.overall_score,
            }
            
            # Adjust according to retry strategyTask
            if self.config.retry_strategy == "partial" and feedback.suggestions:
                # Partial retry: focus only on areas needing improvement
                retry_task["_focus_areas"] = list(feedback.suggestions.keys())
        
        return retry_task
    
    def _handle_timeout(self, last_result: Optional[AgentResult]) -> AgentResult:
        """Handle timeout situation.
        
        Args:
            last_result: Last execution result
            
        Returns:
            Result processed according to on_failure strategy
        """
        if not last_result:
            return AgentResult(
                success=False,
                error_message="No result after all iterations",
            )
        
        if self.config.on_failure == "accept":
            # Accept result, mark as timeout but return
            return AgentResult(
                success=True,
                output={
                    **last_result.output,
                    "_convergence": {
                        "status": "timeout_accepted",
                        "iterations": self.config.max_iterations,
                    }
                },
                error_message=None,
            )
        
        elif self.config.on_failure == "escalate":
            # Escalation handling
            return AgentResult(
                success=False,
                error_message=f"Failed to converge after {self.config.max_iterations} iterations. Escalation required.",
                output=last_result.output,
            )
        
        else:  # retry (default) - return last result
            return last_result
    
    async def execute_multi_agent_with_critic(
        self,
        agent_ids: list[str],
        task: Dict[str, Any],
        aggregate_fn: Callable[[list[AgentResult]], AgentResult],
        on_iteration: Optional[Callable[[int, list[AgentResult], ConvergenceResult], None]] = None,
    ) -> AgentResult:
        """Multi-Agent execution with Critic.
        
        Suitable for MULTI_AGENT mode, all Agent results aggregated and reviewed together.
        
        Args:
            agent_ids: Agent ID list
            task: Task
            aggregate_fn: Result aggregation function
            on_iteration: Callback
            
        Returns:
            Aggregated final result
        """
        iteration = 0
        current_task = task
        last_aggregated: Optional[AgentResult] = None
        
        while iteration < self.config.max_iterations:
            iteration += 1
            
            # Execute all Agents in parallel
            semaphore = asyncio.Semaphore(5)
            
            async def run_with_limit(agent_id: str) -> AgentResult:
                async with semaphore:
                    task_with_idx = {
                        **current_task,
                        "agent_index": agent_ids.index(agent_id),
                    }
                    return await self.runtime.invoke(agent_id, task_with_idx)
            
            results = await asyncio.gather(*[
                run_with_limit(aid) for aid in agent_ids
            ])
            
            # Aggregate results
            aggregated = aggregate_fn(results)
            last_aggregated = aggregated
            
            # Critic review aggregated results
            convergence = self.checker.check(aggregated, iteration)
            
            if on_iteration:
                on_iteration(iteration, results, convergence)
            
            if convergence.converged:
                return aggregated
            
            # Prepare retry
            if iteration < self.config.max_iterations:
                current_task = self._prepare_retry_task(
                    task,
                    convergence.feedback,
                    iteration,
                )
        
        return self._handle_timeout(last_aggregated)