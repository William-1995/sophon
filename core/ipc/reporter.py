"""
Event reporter for skill scripts (child process side).

When SOPHON_REPORT_EVENTS=1 and SOPHON_EVENT_FD is set, skills can emit
structured events to the parent via the pipe. Uses JSON by default;
SOPHON_IPC_FORMAT=msgpack for MessagePack (efficiency).
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_SOPHON_EVENT_KEY = "sophon_event"
_event_file: Any = None


def _get_event_fd() -> int | None:
    fd_str = os.environ.get("SOPHON_EVENT_FD", "")
    if not fd_str:
        return None
    try:
        return int(fd_str)
    except ValueError:
        return None


def _get_format() -> str:
    return (os.environ.get("SOPHON_IPC_FORMAT", "json") or "json").strip().lower()


def _get_event_file():
    """Lazy-open event pipe; keep open for process lifetime."""
    global _event_file
    if _event_file is not None:
        return _event_file
    fd = _get_event_fd()
    if fd is None:
        return None
    if os.environ.get("SOPHON_REPORT_EVENTS", "") != "1":
        return None
    try:
        _event_file = os.fdopen(fd, "wb", closefd=False)
        return _event_file
    except OSError:
        return None


def _serialize_json(event: dict[str, Any]) -> bytes:
    obj = {_SOPHON_EVENT_KEY: event}
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")


def _serialize_msgpack(event: dict[str, Any]) -> bytes:
    try:
        import msgpack
    except ImportError:
        logger.warning("[ipc.reporter] msgpack not installed, falling back to JSON")
        return _serialize_json(event)
    obj = {_SOPHON_EVENT_KEY: event}
    payload = msgpack.packb(obj, use_bin_type=True)
    return len(payload).to_bytes(4, "big") + payload


def _inject_context(event: dict[str, Any]) -> dict[str, Any]:
    """Inject run_id and agent_id from env when not already present."""
    out = dict(event)
    if "run_id" not in out:
        rid = os.environ.get("SOPHON_RUN_ID")
        if rid:
            out["run_id"] = rid
    if "agent_id" not in out:
        aid = os.environ.get("SOPHON_AGENT_ID")
        if aid:
            out["agent_id"] = aid
    return out


def emit_event(event: dict[str, Any]) -> bool:
    """
    Emit an event to the parent process. No-op if event channel is not configured.

    Event should include: type, payload (optional), agent_id (optional), etc.
    run_id and agent_id are auto-injected from SOPHON_RUN_ID/SOPHON_AGENT_ID when set.
    Returns True if emitted, False if channel not available.
    """
    f = _get_event_file()
    if f is None:
        return False
    try:
        event = _inject_context(event)
        fmt = _get_format()
        if fmt == "msgpack":
            data = _serialize_msgpack(event)
        else:
            data = _serialize_json(event)
        f.write(data)
        f.flush()
        return True
    except OSError as e:
        logger.debug("[ipc.reporter] emit failed: %s", e)
        return False
    except Exception as e:
        logger.warning("[ipc.reporter] emit error: %s", e)
        return False


def get_reporter() -> "EventReporter | None":
    """Return an EventReporter if the event channel is configured, else None."""
    if os.environ.get("SOPHON_REPORT_EVENTS", "") != "1":
        return None
    if _get_event_fd() is None:
        return None
    return EventReporter()


class EventReporter:
    """
    Optional event reporter for skills. Use when SOPHON_REPORT_EVENTS=1.

    Skills that support progress can call reporter.emit(type, payload) to
    send events to the parent. If no channel is configured, emit is a no-op.
    """

    def emit(self, event_type: str, payload: dict[str, Any] | None = None, **kwargs: Any) -> bool:
        event: dict[str, Any] = {"type": event_type, **(payload or {}), **kwargs}
        return emit_event(event)
