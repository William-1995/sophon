"""
Excel-Ops - Event emission and executor wrapper.

Provides progress/event emission and execute_skill wrapper that forwards
event_sink, run_id, agent_id for nested skill calls.
"""

import os
from typing import Any

from core.executor import execute_skill
from core.ipc import emit_event, get_reporter


def emit_progress(event_type: str, **payload: Any) -> None:
    """Emit progress/event via reporter if available. Silent on failure."""
    try:
        r = get_reporter()
        if r:
            r.emit(event_type, payload)
    except Exception:
        pass


async def execute_with_events(**kwargs: Any) -> dict[str, Any]:
    """Wrapper that forwards event_sink, run_id, agent_id to execute_skill.

    Args:
        **kwargs: Passed to execute_skill. Overrides event_sink, run_id, agent_id.

    Returns:
        Result from execute_skill.
    """
    kwargs = dict(kwargs)
    kwargs["event_sink"] = (lambda e: emit_event(e)) if get_reporter() else None
    kwargs["run_id"] = os.environ.get("SOPHON_RUN_ID")
    kwargs["agent_id"] = os.environ.get("SOPHON_AGENT_ID") or "excel-ops.fill_by_column"
    return await execute_skill(**kwargs)
