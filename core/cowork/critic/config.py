"""Critic configuration and result definitions.

Supports configurable review strategies and convergence determination.
"""

from dataclasses import dataclass, field
from typing import Any, Dict
from enum import Enum


class CriticStrategy(str, Enum):
    """Critic review strategy."""
    
    STRICT = "strict"
    """Strict mode: must fully satisfy all conditions to pass."""
    
    LENIENT = "lenient"
    """Lenient mode: satisfying most conditions is sufficient to pass."""
    
    ADAPTIVE = "adaptive"
    """Adaptive mode: dynamically adjust standards based on historical performance."""


class OnFailureAction(str, Enum):
    """Handling method when failed."""
    
    RETRY = "retry"
    """Retry: let Agent re-execute task."""
    
    ESCALATE = "escalate"
    """Escalate: hand over to higher-level Agent or human processing."""
    
    ACCEPT = "accept"
    """Accept: accept current result despite not fully converged."""


@dataclass
class CriticConfig:
    """Critic review configuration.
    
    Configurable switches, supports flexible enable/disable for different scenarios.
    """
    
    enabled: bool = True
    """Whether to enable Critic review."""
    
    critic_agent_type: str = "critic"
    """Critic Agent type identifier."""
    
    max_iterations: int = 3
    """Maximum iteration count (including first execution)."""
    
    convergence_threshold: float = 0.8
    """Convergence threshold (0-1), score >= this value considered converged."""
    
    strategy: CriticStrategy = CriticStrategy.STRICT
    """Review strategy."""
    
    on_failure: OnFailureAction = OnFailureAction.RETRY
    """Handling method when convergence not reached."""
    
    retry_strategy: str = "partial"
    """Retry strategy: full, partial."""
    
    check_items: Dict[str, Any] = field(default_factory=dict)
    """Check item definitions, may include:
    - format: format check
    - completeness: completeness check
    - accuracy: accuracy check
    - relevance: relevance check
    """
    
    def should_retry(self, iteration: int) -> bool:
        """Determine whether to continue retrying.
        
        Args:
            iteration: Current iteration count (starting from 1)
            
        Returns:
            Whether to continue retrying
        """
        if not self.enabled:
            return False
        return iteration < self.max_iterations
    
    def is_converged(self, score: float) -> bool:
        """Determine if score meets convergence criteria.
        
        Args:
            score: Score (0-1)
            
        Returns:
            Whether converged
        """
        return score >= self.convergence_threshold


@dataclass
class CritiqueFeedback:
    """Critic review feedback.
    
    Contains score, improvement suggestions, specific issue list.
    """
    
    converged: bool
    """Whether converged."""
    
    overall_score: float
    """Overall score (0-1)."""
    
    feedback: str
    """Improvement suggestion text."""
    
    issues: Dict[str, Any] = field(default_factory=dict)
    """Specific issue list, grouped by category:
    {
        "format": ["Missing title", "Inconsistent formatting"],
        "completeness": ["Missing data source description"],
        "accuracy": [],
        "relevance": [],
    }
    """
    
    suggestions: Dict[str, Any] = field(default_factory=dict)
    """Specific improvement suggestions:
    {
        "add_section": "Add data source section",
        "fix_format": "Unify using Markdown headers",
    }
    """
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata, such as review time, Critic Agent ID, etc."""
    
    def to_retry_task(self) -> Dict[str, Any]:
        """Convert feedback to retry task parameters.
        
        Returns:
            Task parameters containing feedback and suggestions
        """
        return {
            "critique_feedback": self.feedback,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "previous_score": self.overall_score,
        }