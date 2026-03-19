"""
ReAct callback types - typed callbacks for event emission, cancellation, HITL.
"""

from typing import Any, Awaitable, Callable

# Event sink: receives event dict, no return
EventSink = Callable[[dict[str, Any]], None] | None

# Cancel check: no args, returns True if cancelled
CancelCheck = Callable[[], bool] | None

# Decision waiter: (message, choices, *, payload?) -> Awaitable[str]
# Used for HITL when skill requests user confirmation
DecisionWaiter = Callable[..., Awaitable[str]] | None


# Progress callback: (tokens, round_num) -> None
ProgressCallback = Callable[[int, int], None] | None
