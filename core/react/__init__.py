"""
ReAct Engine - Simplified Thought -> Action -> Observation loop.

This package provides a modular ReAct implementation with clear separation
of concerns: preparation, execution, and finalization.

Example:
    from core.react import run_react
    
    answer, metadata = await run_react(
        question="What is the weather?",
        provider=provider,
        workspace_root=Path("/workspace"),
    )
"""

from core.react.main import run_react
from core.react.context import ImmutableRunContext, MutableRunState

__all__ = [
    "run_react",
    "ImmutableRunContext",
    "MutableRunState",
]
