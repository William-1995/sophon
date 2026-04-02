"""Critic module - Review and convergence control.

Provides convergence checking and iteration control.
"""

from core.cowork.critic.status import ConvergenceStatus

from core.cowork.critic.config import (
    CriticConfig,
    CriticStrategy,
    OnFailureAction,
    CritiqueFeedback,
)

from core.cowork.critic.checker import (
    ConvergenceChecker,
    ConvergenceResult,
)

__all__ = [
    # Status
    "ConvergenceStatus",
    # Config
    "CriticConfig",
    "CriticStrategy",
    "OnFailureAction",
    "CritiqueFeedback",
    # Checker
    "ConvergenceChecker",
    "ConvergenceResult",
]
