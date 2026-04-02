"""Workflow Step definition.

Defines step structure in Workflow, supports 4 execution modes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from core.cowork.workflow.modes import ExecutionMode


@dataclass
class AgentConfig:
    """Agent execution configuration."""
    
    agent_type: str
    role: str = "worker"
    initial_memory: Dict[str, Any] = field(default_factory=dict)
    max_turns: int = 5
    can_spawn_children: bool = False


@dataclass
class MultiAgentConfig:
    """Multi-Agent parallel configuration."""
    
    agents: List[Dict[str, Any]]
    """Agent list, each item contains type, role, count.
    
    Example:
        [
            {"type": "researcher", "role": "worker", "count": 3},
            {"type": "analyst", "role": "reviewer", "count": 1},
        ]
    """
    
    aggregate_results: bool = True
    """Whether to aggregate multiple Agent results."""
    
    aggregation_strategy: str = "concat"
    """Aggregation strategy: concat, merge, vote."""


@dataclass
class DiscussionConfig:
    """Discussion mode configuration."""
    
    topic: str
    """Discussion topic."""
    
    participants: List[str]
    """Participant Agent type list."""
    
    max_rounds: int = 3
    """Maximum discussion rounds."""
    
    consensus_required: bool = True
    """Whether consensus is required."""
    
    convergence_criteria: Optional[str] = None
    """Convergence criteria expression (optional)."""


@dataclass
class CriticConfig:
    """Critic review configuration."""
    
    enabled: bool = True
    """Whether to enable Critic review."""
    
    critic_agent_type: str = "critic"
    """Critic Agent type."""
    
    max_iterations: int = 3
    """Maximum iteration count."""
    
    convergence_threshold: float = 0.8
    """Convergence threshold (0-1)."""
    
    on_failure: str = "retry"
    """Failure handling: retry, escalate, accept."""
    
    retry_strategy: str = "partial"
    """Retry strategy: full, partial."""


@dataclass
class WorkflowStep:
    """Workflow step definition."""
    
    step_id: str
    """Step unique identifier."""
    
    name: str
    """Step display name."""
    
    description: Optional[str] = None
    """Step description."""
    
    execution_mode: ExecutionMode = ExecutionMode.TOOL
    """Execution mode."""
    
    # Conditional execution
    condition: Optional[str] = None
    """Execution condition expression (JSONPath style).
    
    Example: "$.steps.prev.output.count > 0"
    """
    
    # TOOL mode configuration
    tool_config: Optional[Dict[str, Any]] = None
    """Tool mode configuration: skill_name, action, arguments."""
    
    # AGENT mode configuration
    agent_config: Optional[AgentConfig] = None
    """Agent mode configuration."""
    
    # MULTI_AGENT mode configuration
    multi_agent_config: Optional[MultiAgentConfig] = None
    """Multi-Agent configuration."""
    
    # DISCUSSION mode configuration
    discussion_config: Optional[DiscussionConfig] = None
    """Discussion mode configuration."""
    
    # Critic configuration (supported by all modes)
    critic_config: Optional[CriticConfig] = None
    """Critic review configuration."""
    
    # Input/output definition
    input_schema: Dict[str, Any] = field(default_factory=dict)
    """Input parameter definition."""
    
    output_schema: Dict[str, Any] = field(default_factory=dict)
    """Output parameter definition."""
    
    # Timeout configuration
    timeout_seconds: int = 300
    """Step timeout (seconds)."""
    
    def validate(self) -> List[str]:
        """Validate configuration, return error list (empty means valid)."""
        errors = []
        
        # Check required configuration based on execution mode
        if self.execution_mode == ExecutionMode.TOOL:
            if not self.tool_config:
                errors.append("TOOL mode requires tool_config")
        
        elif self.execution_mode == ExecutionMode.AGENT:
            if not self.agent_config:
                errors.append("AGENT mode requires agent_config")
        
        elif self.execution_mode == ExecutionMode.MULTI_AGENT:
            if not self.multi_agent_config:
                errors.append("MULTI_AGENT mode requires multi_agent_config")
            elif not self.multi_agent_config.agents:
                errors.append("multi_agent_config.agents cannot be empty")
        
        elif self.execution_mode == ExecutionMode.DISCUSSION:
            if not self.discussion_config:
                errors.append("DISCUSSION mode requires discussion_config")
            elif not self.discussion_config.participants:
                errors.append("discussion_config.participants cannot be empty")
        
        return errors


@dataclass
class WorkflowDefinition:
    """Workflow definition."""
    
    workflow_id: str
    """Workflow unique identifier."""
    
    name: str
    """Workflow name."""
    
    description: Optional[str] = None
    """Workflow description."""
    
    
    steps: List[WorkflowStep] = field(default_factory=list)
    """Step list (ordered)."""
    
    # Input/output definition
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    
    # Global configuration
    cleanup_policy: Dict[str, Any] = field(default_factory=lambda: {
        "on_success": "delete_intermediate",
        "on_failure": "preserve_all",
        "retention_hours": 24,
    })
    
    tags: List[str] = field(default_factory=list)
    """Tags for classification and retrieval."""
    
    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        """Get step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None
    
    def validate(self) -> List[str]:
        """Validate entire workflow."""
        errors = []
        
        if not self.steps:
            errors.append("Workflow requires at least 1 step")
        
        step_ids = set()
        for step in self.steps:
            if step.step_id in step_ids:
                errors.append(f"Duplicate step_id: {step.step_id}")
            step_ids.add(step.step_id)
            
            # Validate each step
            step_errors = step.validate()
            for err in step_errors:
                errors.append(f"Step {step.step_id}: {err}")
        
        return errors