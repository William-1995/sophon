"""Convergence Checker - Simple convergence evaluation.

Evaluates if agent results meet convergence criteria.
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass

from core.cowork.critic.status import ConvergenceStatus
from core.cowork.critic.config import CriticConfig, CritiqueFeedback


@dataclass
class ConvergenceResult:
    """Convergence check result."""
    converged: bool
    status: ConvergenceStatus
    score: float
    feedback: Optional[CritiqueFeedback] = None
    reasoning: str = ""


class ConvergenceChecker:
    """Checks if agent outputs have converged.
    
    Simple implementation for new architecture.
    """
    
    def __init__(self, config: CriticConfig):
        self.config = config
    
    def check(self, result: Dict[str, Any]) -> ConvergenceResult:
        """Check if result meets convergence criteria.
        
        Args:
            result: Agent execution result
            
        Returns:
            Convergence evaluation
        """
        # Simple pass-through for now
        # In production, this would evaluate quality, completeness, etc.
        return ConvergenceResult(
            converged=True,
            status=ConvergenceStatus.CONVERGED,
            score=1.0,
            reasoning="Convergence checking disabled in new architecture",
        )
