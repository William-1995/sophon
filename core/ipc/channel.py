"""
Pipe-based event channel. Cross-platform (pipe works on Windows, macOS, Linux).

Parent: reads from pipe, parses frames, yields events (objects with sophon_event).
Child: writes {"sophon_event": event} to pipe via reporter.
"""

import asyncio
import logging
import os
import threading
from collections.abc import AsyncIterator
from queue import Empty, Queue
from typing import Any

from constants import IPC_BUFFER_READ_SIZE
from core.ipc.serializers import JsonSerializer, MessagePackSerializer

logger = logging.getLogger(__name__)

SOPHON_EVENT_KEY = "sophon_event"
IPC_FORMAT_JSON = "json"
IPC_FORMAT_MSGPACK = "msgpack"
_SENTINEL = object()


def _get_serializer(format_name: str) -> JsonSerializer | MessagePackSerializer:
    if format_name == IPC_FORMAT_MSGPACK:
        return MessagePackSerializer()
    return JsonSerializer()


def _reader_thread(
    read_fd: int,
    serializer: JsonSerializer | MessagePackSerializer,
    queue: Queue,
) -> None:
    """Blocking read loop; parses frames and puts events in queue."""
    buffer = bytearray()
    use_json = isinstance(serializer, JsonSerializer)
    try:
        with os.fdopen(read_fd, "rb", closefd=True) as f:
            while True:
                chunk = f.read(IPC_BUFFER_READ_SIZE)
                if not chunk:
                    break
                buffer.extend(chunk)
                while True:
                    if use_json:
                        line_end = buffer.find(b"\n")
                        if line_end < 0:
                            break
                        line = bytes(buffer[: line_end + 1])
                        del buffer[: line_end + 1]
                        obj = serializer.unpack(line)
                    else:
                        if len(buffer) < 4:
                            break
                        length = int.from_bytes(buffer[:4], "big")
                        if len(buffer) < 4 + length:
                            break
                        frame = bytes(buffer[: 4 + length])
                        del buffer[: 4 + length]
                        obj = serializer.unpack(frame)
                    if obj and SOPHON_EVENT_KEY in obj:
                        queue.put(obj[SOPHON_EVENT_KEY])
    except OSError as e:
        logger.debug("[ipc] reader_thread fd=%s stopped: %s", read_fd, e)
    finally:
        queue.put(_SENTINEL)


class PipeEventChannel:
    """
    Read events from a pipe. Used by parent process.
    Yields dicts (sophon_event value). Thread-based reader for cross-platform reliability.
    """

    def __init__(
        self,
        read_fd: int,
        format_name: str = IPC_FORMAT_JSON,
    ) -> None:
        self._read_fd = read_fd
        self._serializer = _get_serializer(format_name)
        self._queue: Queue = Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the reader thread. Call before read_events."""
        self._thread = threading.Thread(
            target=_reader_thread,
            args=(self._read_fd, self._serializer, self._queue),
            daemon=True,
        )
        self._thread.start()

    async def read_events(self) -> AsyncIterator[dict[str, Any]]:
        """Async generator yielding event payloads (sophon_event value)."""
        if self._thread is None:
            self.start()
        while True:
            try:
                item = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._queue.get(timeout=0.5),
                )
            except Empty:
                continue
            if item is _SENTINEL:
                break
            yield item
