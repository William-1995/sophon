"""
Serializers for IPC: JSON (default) and MessagePack.

JSON: NDJSON over pipe (one object per line). Human-readable, cross-tool.
MessagePack: length-prefixed binary frames. More efficient.
"""

import json
import struct
from abc import ABC, abstractmethod
from typing import Any

from constants import IPC_MESSAGE_LENGTH_PREFIX_BYTES


class BaseSerializer(ABC):
    """Base interface for pack/unpack."""

    @abstractmethod
    def pack(self, obj: dict[str, Any]) -> bytes:
        """Serialize object to bytes for pipe write."""
        pass

    @abstractmethod
    def unpack(self, data: bytes) -> dict[str, Any] | None:
        """Deserialize bytes to object. Returns None if incomplete/invalid."""
        pass


class JsonSerializer(BaseSerializer):
    """NDJSON: one JSON object per line. Default, human-readable."""

    def pack(self, obj: dict[str, Any]) -> bytes:
        return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")

    def unpack(self, data: bytes) -> dict[str, Any] | None:
        line = data.decode("utf-8", errors="replace").strip()
        if not line:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None


class MessagePackSerializer(BaseSerializer):
    """Length-prefixed MessagePack: 4-byte big-endian length + payload. Efficient."""

    def __init__(self) -> None:
        try:
            import msgpack
            self._msgpack = msgpack
        except ImportError:
            raise ImportError("msgpack required for MessagePackSerializer. Run: pip install msgpack")

    def pack(self, obj: dict[str, Any]) -> bytes:
        payload = self._msgpack.packb(obj, use_bin_type=True)
        return struct.pack(">I", len(payload)) + payload

    def unpack(self, data: bytes) -> dict[str, Any] | None:
        if len(data) < IPC_MESSAGE_LENGTH_PREFIX_BYTES:
            return None
        length = struct.unpack(">I", data[:IPC_MESSAGE_LENGTH_PREFIX_BYTES])[0]
        need = IPC_MESSAGE_LENGTH_PREFIX_BYTES + length
        if len(data) < need:
            return None
        payload = data[IPC_MESSAGE_LENGTH_PREFIX_BYTES:need]
        try:
            return self._msgpack.unpackb(payload, raw=False)
        except Exception:
            return None
