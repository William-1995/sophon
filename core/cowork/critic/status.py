"""Convergence status management.

Defines various states of convergence/divergence.
"""

from enum import Enum


class ConvergenceStatus(str, Enum):
    """Convergence status enumeration."""
    
    NOT_STARTED = "not_started"
    """Review not started."""
    
    IN_PROGRESS = "in_progress"
    """Review in progress, not yet converged."""
    
    CONVERGED = "converged"
    """Converged, meets quality standards."""
    
    DIVERGED = "diverged"
    """Diverged, still not meeting standards after multiple attempts."""
    
    TIMEOUT = "timeout"
    """Timeout, reached maximum iterations."""
    
    MANUAL_ACCEPT = "manual_accept"
    """Manually accepted, despite not automatically converged."""
