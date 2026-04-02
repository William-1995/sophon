"""Message Bus - Inter-Agent communication infrastructure.

Phase 1 implementation: In-memory version supporting point-to-point, broadcast, and subscription modes.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import asyncio


class MessageType(str, Enum):
    """Message type enumeration."""
    
    TASK = "task"           # Task assignment
    RESULT = "result"       # Task result
    CRITIQUE = "critique"   # Critique feedback
    CONSENSUS = "consensus" # Consensus reached
    BROADCAST = "broadcast" # Broadcast message
    DIRECT = "direct"       # Point-to-point


@dataclass(frozen=True)
class Message:
    """Message data class.
    
    Attributes:
        message_id: Unique identifier
        sender: Sender agent_id
        receiver: Receiver agent_id, None for broadcast
        type: Message type
        payload: Message content
        timestamp: Send time
        thread_id: Discussion thread ID
    """
    
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    sender: str = ""
    receiver: Optional[str] = None
    type: MessageType = MessageType.DIRECT
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    thread_id: Optional[str] = None


class MessageBus(ABC):
    """Message bus abstract interface.
    
    Supports asynchronous inter-Agent communication, decouples data flow.
    """
    
    @abstractmethod
    async def send(self, message: Message) -> None:
        """Send message to specified receiver.
        
        Args:
            message: Message to send
            
        Raises:
            ValueError: Receiver does not exist
        """
        pass
    
    @abstractmethod
    async def broadcast(self, message: Message) -> None:
        """Broadcast message to all subscribers.
        
        Args:
            message: Message to broadcast, receiver should be None
        """
        pass
    
    @abstractmethod
    async def subscribe(self, agent_id: str, handler: Callable[[Message], None]) -> None:
        """Subscribe to messages.
        
        Args:
            agent_id: Subscriber ID
            handler: Message handler callback
        """
        pass
    
    @abstractmethod
    async def unsubscribe(self, agent_id: str) -> None:
        """Unsubscribe.
        
        Args:
            agent_id: Subscriber ID to cancel
        """
        pass
    
    @abstractmethod
    async def get_inbox(self, agent_id: str) -> List[Message]:
        """Get inbox for specified agent.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of all messages received by this agent
        """
        pass
    
    @abstractmethod
    async def get_thread(self, thread_id: str) -> List[Message]:
        """Get all messages in discussion thread.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            List of all messages in this thread
        """
        pass
    
    @abstractmethod
    async def clear_inbox(self, agent_id: str) -> None:
        """Clear inbox for specified agent.
        
        Args:
            agent_id: Agent ID
        """
        pass


class InMemoryMessageBus(MessageBus):
    """In-memory message bus implementation.
    
    Implemented using asyncio.Queue, suitable for single-machine deployment.
    Thread-safe but not persistent.
    """
    
    def __init__(self):
        self._subscribers: Dict[str, Callable[[Message], None]] = {}
        self._inboxes: Dict[str, List[Message]] = {}
        self._threads: Dict[str, List[Message]] = {}
        self._lock = asyncio.Lock()
    
    async def send(self, message: Message) -> None:
        """Send point-to-point message."""
        if message.receiver is None:
            raise ValueError("Direct message must have receiver")
        
        async with self._lock:
            # Store to inbox
            if message.receiver not in self._inboxes:
                self._inboxes[message.receiver] = []
            self._inboxes[message.receiver].append(message)
            
            # Store to thread
            if message.thread_id:
                if message.thread_id not in self._threads:
                    self._threads[message.thread_id] = []
                self._threads[message.thread_id].append(message)
            
            # Trigger callback
            handler = self._subscribers.get(message.receiver)
            if handler:
                try:
                    handler(message)
                except Exception:
                    # Callback exceptions do not interrupt message delivery
                    pass
    
    async def broadcast(self, message: Message) -> None:
        """Broadcast message."""
        if message.receiver is not None:
            raise ValueError("Broadcast message should not have specific receiver")
        
        async with self._lock:
            # Store to all subscribers' inboxes
            for agent_id in self._subscribers:
                if agent_id == message.sender:
                    continue  # Do not send to self
                    
                if agent_id not in self._inboxes:
                    self._inboxes[agent_id] = []
                self._inboxes[agent_id].append(message)
            
            # Store to thread
            if message.thread_id:
                if message.thread_id not in self._threads:
                    self._threads[message.thread_id] = []
                self._threads[message.thread_id].append(message)
            
            # Trigger all callbacks
            for agent_id, handler in self._subscribers.items():
                if agent_id == message.sender:
                    continue
                try:
                    handler(message)
                except Exception:
                    pass
    
    async def subscribe(self, agent_id: str, handler: Callable[[Message], None]) -> None:
        """Subscribe to messages."""
        async with self._lock:
            self._subscribers[agent_id] = handler
            if agent_id not in self._inboxes:
                self._inboxes[agent_id] = []
    
    async def unsubscribe(self, agent_id: str) -> None:
        """Unsubscribe."""
        async with self._lock:
            self._subscribers.pop(agent_id, None)
    
    async def get_inbox(self, agent_id: str) -> List[Message]:
        """Get inbox."""
        async with self._lock:
            return list(self._inboxes.get(agent_id, []))
    
    async def get_thread(self, thread_id: str) -> List[Message]:
        """Get thread messages."""
        async with self._lock:
            return list(self._threads.get(thread_id, []))
    
    async def clear_inbox(self, agent_id: str) -> None:
        """Clear inbox."""
        async with self._lock:
            if agent_id in self._inboxes:
                self._inboxes[agent_id].clear()
    
    async def get_subscriber_count(self) -> int:
        """Get subscriber count (for testing)."""
        async with self._lock:
            return len(self._subscribers)
    
    async def reset(self) -> None:
        """Reset all states (for testing)."""
        async with self._lock:
            self._subscribers.clear()
            self._inboxes.clear()
            self._threads.clear()