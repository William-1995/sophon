"""
ReAct Types - Type aliases for ReAct module.

Centralizes type definitions to avoid circular imports and improve readability.
"""

from collections.abc import Awaitable, Callable
from typing import Any

# Callback type for progress updates: (total_tokens, round_num)
ProgressCallback = Callable[[int, int | None], None]

# Callback for event emission: receives event dict
EventSink = Callable[[dict[str, Any]], None]

# Callback for cancellation check: returns True if should cancel
CancelCheck = Callable[[], bool]

# Callback for HITL decision: (message, choices) -> selected choice
DecisionWaiter = Callable[[str, list[str]], Awaitable[str]]

# Type alias for tool call structure: (skill_name, action, arguments)
ToolCall = tuple[str, str, dict]

# Type alias for reference structure from tools
Reference = dict[str, Any]
