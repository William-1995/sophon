"""
IPC - Subprocess event channel for skill progress reporting.

Cross-platform pipe-based communication. Supports JSON (default) and MessagePack.
Skills optionally emit events; parent process reads and forwards to event_sink.
"""

from core.ipc.channel import PipeEventChannel
from core.ipc.reporter import emit_event, get_reporter
from core.ipc.serializers import JsonSerializer, MessagePackSerializer

get_event_reporter = get_reporter  # alias

__all__ = [
    "PipeEventChannel",
    "emit_event",
    "get_reporter",
    "get_event_reporter",
    "JsonSerializer",
    "MessagePackSerializer",
]
