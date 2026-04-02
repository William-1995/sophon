"""Workflow state management.

Manages Workflow runtime state, including steps, agents, messages.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import uuid

from core.cowork.workflow.modes import StepStatus, WorkflowStatus


class ConvergenceStatus(str, Enum):
    """Convergence status."""
    
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    CONVERGED = "converged"
    DIVERGED = "diverged"
    TIMEOUT = "timeout"


@dataclass
class StepState:
    """Step runtime state."""
    
    step_id: str
    name: str = ""  # Step name
    status: StepStatus = StepStatus.PENDING
    agent_id: Optional[str] = None  # If AGENT mode
    agent_ids: List[str] = field(default_factory=list)  # If MULTI_AGENT mode
    execution_mode: str = "tool"
    
    # Input/output
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    
    # Execution record
    created_at: Optional[str] = None  # ISO format string
    started_at: Optional[str] = None  # ISO format string
    completed_at: Optional[str] = None  # ISO format string
    error_message: Optional[str] = None
    retry_count: int = 0
    
    # Critic related
    convergence_status: ConvergenceStatus = ConvergenceStatus.NOT_STARTED
    critique_feedback: Optional[str] = None
    
    def mark_started(self) -> None:
        """Mark as started."""
        self.status = StepStatus.RUNNING
        self.started_at = datetime.utcnow().isoformat()
    
    def mark_completed(self, output: Dict[str, Any]) -> None:
        """Mark execution completed."""
        self.status = StepStatus.COMPLETED
        self.output_data = output
        self.completed_at = datetime.utcnow().isoformat()
    
    def mark_failed(self, error: str) -> None:
        """Mark execution failed."""
        self.status = StepStatus.FAILED
        self.error_message = error
        self.completed_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "status": self.status.value,
            "agent_id": self.agent_id,
            "agent_ids": self.agent_ids,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "convergence_status": self.convergence_status.value,
            "critique_feedback": self.critique_feedback,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StepState":
        """Create from dictionary."""
        step = cls(
            step_id=data["step_id"],
            name=data.get("name", ""),
            status=StepStatus(data.get("status", "pending")),
            agent_id=data.get("agent_id"),
            agent_ids=data.get("agent_ids", []),
            input_data=data.get("input_data", {}),
            output_data=data.get("output_data", {}),
            retry_count=data.get("retry_count", 0),
            convergence_status=ConvergenceStatus(data.get("convergence_status", "not_started")),
            critique_feedback=data.get("critique_feedback"),
        )
        # Parse timestamps (already in ISO format strings)
        step.created_at = data.get("created_at")
        step.started_at = data.get("started_at")
        step.completed_at = data.get("completed_at")
        if data.get("error_message"):
            step.error_message = data["error_message"]
        return step


@dataclass
class AgentState:
    """Agent runtime state (for Workflow tracking)."""
    
    agent_id: str
    agent_type: str
    role: str
    step_id: str
    status: str = "idle"
    current_task: Optional[str] = None
    
    # Statistics
    message_count: int = 0
    task_count: int = 0
    
    spawned_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_active: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "role": self.role,
            "step_id": self.step_id,
            "status": self.status,
            "current_task": self.current_task,
            "message_count": self.message_count,
            "task_count": self.task_count,
            "spawned_at": self.spawned_at,
            "last_active": self.last_active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentState":
        return cls(
            agent_id=data.get("agent_id", ""),
            agent_type=data.get("agent_type", ""),
            role=data.get("role", ""),
            step_id=data.get("step_id", ""),
            status=data.get("status", "idle"),
            current_task=data.get("current_task"),
            message_count=int(data.get("message_count", 0)),
            task_count=int(data.get("task_count", 0)),
            spawned_at=data.get("spawned_at", datetime.utcnow().isoformat()),
            last_active=data.get("last_active", datetime.utcnow().isoformat()),
        )

@dataclass
class MessageEntry:
    """Message record (for audit)."""
    
    message_id: str
    sender: str
    receiver: Optional[str]
    type: str
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    thread_id: Optional[str] = None


    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "type": self.type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "thread_id": self.thread_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessageEntry":
        return cls(
            message_id=data.get("message_id", ""),
            sender=data.get("sender", ""),
            receiver=data.get("receiver"),
            type=data.get("type", ""),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            thread_id=data.get("thread_id"),
        )

@dataclass
class ThreadState:
    """Discussion thread state."""
    
    thread_id: str
    topic: str
    participant_ids: List[str]
    messages: List[MessageEntry] = field(default_factory=list)
    
    # Convergence status
    consensus_reached: bool = False
    consensus_result: Optional[Dict[str, Any]] = None
    
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None


    def to_dict(self) -> Dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "topic": self.topic,
            "participant_ids": self.participant_ids,
            "message_count": len(self.messages),
            "consensus_reached": self.consensus_reached,
            "consensus_result": self.consensus_result,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "messages": [msg.to_dict() for msg in self.messages],
        }


@dataclass
class TimelineEvent:
    event_id: str
    event_type: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    step_id: Optional[str] = None
    agent_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "step_id": self.step_id,
            "agent_id": self.agent_id,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimelineEvent":
        return cls(
            event_id=data.get("event_id", ""),
            event_type=data.get("event_type", ""),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
            step_id=data.get("step_id"),
            agent_id=data.get("agent_id"),
            payload=data.get("payload", {}),
        )

@dataclass
class WorkflowState:
    """Workflow Runtime state."""
    
    # Basic info
    workflow_id: str
    instance_id: str
    status: WorkflowStatus = WorkflowStatus.QUEUED
    
    # Step Status
    steps: Dict[str, StepState] = field(default_factory=dict)
    current_step_id: Optional[str] = None
    
    # Agent Tracking
    agents: Dict[str, AgentState] = field(default_factory=dict)
    
    # Message audit
    messages: List[MessageEntry] = field(default_factory=list)
    
    # Discussion thread
    threads: Dict[str, ThreadState] = field(default_factory=dict)

    # Timeline event (for UI replay agent interactions)
    timeline: List["TimelineEvent"] = field(default_factory=list)
    
    # Convergence tracking
    iterations: Dict[str, int] = field(default_factory=dict)
    convergence_status: Dict[str, ConvergenceStatus] = field(default_factory=dict)
    
    # Global input/output
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    batch_progress: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps (ISO format strings)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # Error message
    error_message: Optional[str] = None
    
    def get_step(self, step_id: str) -> Optional[StepState]:
        """Get Step state."""
        return self.steps.get(step_id)
    
    def add_step(self, step_id: str, name: str = "") -> StepState:
        """Add Step state."""
        if step_id not in self.steps:
            self.steps[step_id] = StepState(step_id=step_id, name=name)
        return self.steps[step_id]
    
    def add_agent(self, agent_id: str, agent_type: str, role: str, step_id: str) -> AgentState:
        """Add Agent tracking."""
        agent = AgentState(
            agent_id=agent_id,
            agent_type=agent_type,
            role=role,
            step_id=step_id,
        )
        self.agents[agent_id] = agent
        return agent
    
    def add_message(self, message: MessageEntry) -> None:
        """Record message."""
        from datetime import datetime
        self.messages.append(message)
        
        # Update related agent message count
        now = datetime.utcnow().isoformat()
        if message.sender in self.agents:
            self.agents[message.sender].message_count += 1
            self.agents[message.sender].last_active = now
        if message.receiver and message.receiver in self.agents:
            self.agents[message.receiver].message_count += 1
            self.agents[message.receiver].last_active = now
    
    def add_thread(self, thread_id: str, topic: str, participants: List[str]) -> ThreadState:
        """Add discussion thread."""
        thread = ThreadState(
            thread_id=thread_id,
            topic=topic,
            participant_ids=participants,
        )
        self.threads[thread_id] = thread
        return thread

    def add_timeline_event(
        self,
        event_type: str,
        step_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> "TimelineEvent":
        event = TimelineEvent(
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            event_type=event_type,
            step_id=step_id,
            agent_id=agent_id,
            payload=payload or {},
        )
        self.timeline.append(event)
        return event
    

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "instance_id": self.instance_id,
            "status": self.status.value,
            "steps": {
                sid: step.to_dict()
                for sid, step in self.steps.items()
            },
            "agents": {
                aid: agent.to_dict()
                for aid, agent in self.agents.items()
            },
            "messages": [msg.to_dict() for msg in self.messages],
            "threads": {
                tid: thread.to_dict()
                for tid, thread in self.threads.items()
            },
            "timeline": [event.to_dict() for event in self.timeline],
            "current_step_id": self.current_step_id,
            "batch_progress": self.batch_progress,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
        }
