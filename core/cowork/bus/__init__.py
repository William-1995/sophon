"""Co-work Bus module.

Message Bus infrastructure supporting asynchronous inter-Agent communication.
"""

from core.cowork.bus.message import (
    Message,
    MessageType,
    MessageBus,
    InMemoryMessageBus,
)

__all__ = [
    "Message",
    "MessageType",
    "MessageBus",
    "InMemoryMessageBus",
]