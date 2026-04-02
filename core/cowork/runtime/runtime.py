"""Manage agent lifecycle, execution, and message-bus integration.

This runtime keeps per-agent contexts in memory, dispatches tasks to registered
executors, tracks status transitions, and exposes convenience wrappers for direct
or broadcast messaging via ``MessageBus``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from core.cowork.bus import Message, MessageBus, MessageType

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Lifecycle status values for an agent context."""

    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    DEAD = "dead"


@dataclass
class AgentContext:
    """Mutable runtime state for one spawned agent.

    Attributes:
        agent_id (str): Unique runtime id (e.g. ``type_ab12cd34``).
        agent_type (str): Executor registry key for this agent.
        role (str): Human-readable role label used by higher-level workflows.
        instance_id (str): Parent workflow/runtime instance id.
        status (AgentStatus): Current lifecycle status.
        memory (Dict[str, Any]): Agent-local mutable state bag.
        current_task (Optional[str]): Current task id while working.
        spawned_at (datetime): Agent creation time (UTC).
        last_active (datetime): Last activity timestamp (UTC).
    """

    agent_id: str
    agent_type: str
    role: str
    instance_id: str

    status: AgentStatus = field(default=AgentStatus.IDLE)
    memory: Dict[str, Any] = field(default_factory=dict)
    current_task: Optional[str] = None
    spawned_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)

    def update_activity(self) -> None:
        """Refresh ``last_active`` to current UTC time."""
        self.last_active = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context fields for diagnostics or API payloads.

        Returns:
            Dict[str, Any]: JSON-compatible representation.
        """
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "role": self.role,
            "instance_id": self.instance_id,
            "status": self.status.value,
            "memory": self.memory,
            "current_task": self.current_task,
            "spawned_at": self.spawned_at.isoformat(),
            "last_active": self.last_active.isoformat(),
        }


@dataclass
class AgentResult:
    """Result payload returned by executor invocation.

    Attributes:
        success (bool): Whether the task completed successfully.
        output (Dict[str, Any]): Arbitrary structured executor output.
        error_message (Optional[str]): Error details when ``success`` is False.
        execution_time_ms (int): Wall-clock runtime measured by ``AgentRuntime``.
    """

    success: bool
    output: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    execution_time_ms: int = 0


class AgentExecutor(ABC):
    """Abstract executor contract implemented per agent type."""

    @abstractmethod
    async def execute(
        self,
        context: AgentContext,
        task: Dict[str, Any],
    ) -> AgentResult:
        """Run one task for the provided agent context.

        Args:
            context (AgentContext): Runtime context for the target agent.
            task (Dict[str, Any]): Task payload (schema defined by concrete executor).

        Returns:
            AgentResult: Execution outcome and output payload.
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """List capability names exposed by this executor.

        Returns:
            List[str]: Capability identifiers.
        """
        pass


class AgentRuntime:
    """Coordinate agent lifecycle, task dispatch, and messaging."""

    def __init__(self, message_bus: MessageBus):
        """Initialize runtime with a shared message bus.

        Args:
            message_bus (MessageBus): Bus used for inbox/thread and publish/subscribe.
        """
        self._bus = message_bus
        self._agents: Dict[str, AgentContext] = {}
        self._executors: Dict[str, AgentExecutor] = {}
        self._lock = asyncio.Lock()

    def register_executor(self, agent_type: str, executor: AgentExecutor) -> None:
        """Register or replace an executor implementation by agent type.

        Args:
            agent_type (str): Type key used during ``spawn`` and ``invoke``.
            executor (AgentExecutor): Concrete executor instance.
        """
        self._executors[agent_type] = executor

    def _resolve_executor(self, agent_type: str) -> AgentExecutor | None:
        """Return registered executor for ``agent_type`` when available."""
        return self._executors.get(agent_type)

    async def _update_context(self, agent_id: str, **updates: Any) -> Optional[AgentContext]:
        """Apply in-place field updates and touch activity timestamp.

        Args:
            agent_id (str): Target agent id.
            **updates (Any): Field/value pairs set via ``setattr``.

        Returns:
            Optional[AgentContext]: Updated context, or ``None`` if missing.
        """
        async with self._lock:
            context = self._agents.get(agent_id)
            if not context:
                return None
            for key, value in updates.items():
                setattr(context, key, value)
            context.update_activity()
            return context

    async def spawn(
        self,
        agent_type: str,
        role: str,
        instance_id: str,
        initial_memory: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new agent context and subscribe it to message updates.

        Args:
            agent_type (str): Registered executor type key.
            role (str): Human-readable role label.
            instance_id (str): Parent workflow/runtime instance id.
            initial_memory (Optional[Dict[str, Any]]): Initial memory snapshot.

        Returns:
            str: Generated ``agent_id``.

        Raises:
            ValueError: If ``agent_type`` has no registered executor.
        """
        if agent_type not in self._executors:
            raise ValueError(f"Unknown agent type: {agent_type}")

        agent_id = f"{agent_type}_{uuid.uuid4().hex[:8]}"
        context = AgentContext(
            agent_id=agent_id,
            agent_type=agent_type,
            role=role,
            instance_id=instance_id,
            memory=initial_memory or {},
        )

        async with self._lock:
            self._agents[agent_id] = context

        await self._bus.subscribe(agent_id, self._create_message_handler(agent_id))
        return agent_id

    async def kill(self, agent_id: str) -> None:
        """Mark and remove an agent, then unsubscribe from bus delivery.

        Args:
            agent_id (str): Agent id to remove.
        """
        async with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].status = AgentStatus.DEAD
                del self._agents[agent_id]
        await self._bus.unsubscribe(agent_id)

    async def invoke(self, agent_id: str, task: Dict[str, Any]) -> AgentResult:
        """Execute one task on an existing agent and update lifecycle status.

        Args:
            agent_id (str): Agent id to invoke.
            task (Dict[str, Any]): Executor-specific task payload.

        Returns:
            AgentResult: Executor result (or guarded failure result).

        Raises:
            ValueError: If agent does not exist or is already dead.
        """
        async with self._lock:
            context = self._agents.get(agent_id)
            if not context:
                raise ValueError(f"Agent not found: {agent_id}")
            if context.status == AgentStatus.DEAD:
                raise ValueError(f"Agent is dead: {agent_id}")
            context.status = AgentStatus.WORKING
            context.current_task = task.get("task_id", "unknown")

        executor = self._resolve_executor(context.agent_type)
        if not executor:
            return AgentResult(success=False, error_message=f"No executor for type: {context.agent_type}")

        start_time = datetime.utcnow()
        result = AgentResult(success=False)
        try:
            executor_result = await executor.execute(context, task)
            if executor_result is None:
                logger.error("Executor returned None for agent_type=%s", context.agent_type)
                result = AgentResult(success=False, error_message="Executor returned None")
            else:
                result = executor_result
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            logger.exception("Executor exception for agent_id=%s", agent_id)
            result = AgentResult(success=False, error_message=str(exc))
        finally:
            result.execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            await self._update_context(
                agent_id,
                status=AgentStatus.IDLE if result.success else AgentStatus.WAITING,
                current_task=None,
            )

        return result

    async def get_context(self, agent_id: str) -> Optional[AgentContext]:
        """Return context for one agent.

        Args:
            agent_id (str): Agent id.

        Returns:
            Optional[AgentContext]: Context when found, else ``None``.
        """
        async with self._lock:
            return self._agents.get(agent_id)

    async def get_all_agents(self) -> List[AgentContext]:
        """Return a snapshot list of all active agent contexts."""
        async with self._lock:
            return list(self._agents.values())

    async def get_agents_by_instance(self, instance_id: str) -> List[AgentContext]:
        """Return agents that belong to a specific runtime instance.

        Args:
            instance_id (str): Parent workflow/runtime instance id.

        Returns:
            List[AgentContext]: Matching agent contexts.
        """
        async with self._lock:
            return [ctx for ctx in self._agents.values() if ctx.instance_id == instance_id]

    async def get_inbox(self, agent_id: str) -> List[Message]:
        """Proxy inbox lookup from ``MessageBus`` for one agent."""
        return await self._bus.get_inbox(agent_id)

    async def get_thread(self, thread_id: str) -> List[Message]:
        """Proxy thread lookup from ``MessageBus`` by thread id."""
        return await self._bus.get_thread(thread_id)

    async def clear_inbox(self, agent_id: str) -> None:
        """Clear buffered inbox messages for one agent."""
        await self._bus.clear_inbox(agent_id)

    async def send_message_to(self, from_agent: str, to_agent: str, payload: Dict[str, Any]) -> None:
        """Send a direct message from one agent to another.

        Args:
            from_agent (str): Sender agent id.
            to_agent (str): Receiver agent id.
            payload (Dict[str, Any]): Message body.
        """
        await self._bus.send(
            Message(
                sender=from_agent,
                receiver=to_agent,
                type=MessageType.DIRECT,
                payload=payload,
            )
        )

    async def broadcast_message(self, from_agent: str, payload: Dict[str, Any]) -> None:
        """Broadcast a message from one agent to all subscribers.

        Args:
            from_agent (str): Sender agent id.
            payload (Dict[str, Any]): Broadcast body.
        """
        await self._bus.broadcast(
            Message(
                sender=from_agent,
                receiver=None,
                type=MessageType.BROADCAST,
                payload=payload,
            )
        )

    def _create_message_handler(self, agent_id: str) -> Callable[[Message], None]:
        """Create subscriber callback that updates ``last_active`` on message arrival.

        Args:
            agent_id (str): Agent id bound to this handler.

        Returns:
            Callable[[Message], None]: Message callback function.
        """
        def handler(_message: Message) -> None:
            asyncio.create_task(self._update_context(agent_id))

        return handler

    async def cleanup_dead_agents(self) -> int:
        """Remove all contexts currently marked as ``DEAD``.

        Returns:
            int: Number of removed agents.
        """
        async with self._lock:
            dead_agents = [
                agent_id
                for agent_id, context in self._agents.items()
                if context.status == AgentStatus.DEAD
            ]

        for agent_id in dead_agents:
            await self.kill(agent_id)

        return len(dead_agents)
