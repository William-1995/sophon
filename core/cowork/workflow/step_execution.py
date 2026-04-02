"""Workflow step execution helpers.

This module keeps per-step prompt assembly and mode-specific dispatch out of the
workflow engine so the engine can stay focused on orchestration/state changes.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from constants import DEFAULT_USER_ID
from core.cowork.agent_base import AgentOutput, AgentStatus
from core.cowork.workflow.analysis import extract_batch_summary, task_requests_file_output
from core.cowork.workflow.modes import ExecutionMode
from core.cowork.workflow.prompt_parts import (
    build_batch_fragment,
    build_context_fragment,
    build_cumulative_context,
    build_file_output_fragment,
    build_step_header_fragment,
    build_system_extra_prefix,
)
from core.cowork.workflow.state import MessageEntry, StepState, WorkflowState
from core.react import run_react
from providers import get_provider

logger = logging.getLogger(__name__)


class WorkflowStepExecution:
    """Encapsulates step-mode dispatch and ReAct prompt assembly."""

    def __init__(
        self,
        workspace_root: Path,
        db_path: Path,
    ) -> None:
        self._workspace_root = workspace_root
        self._db_path = db_path

    def resolve_execution_mode(self, step: StepState) -> ExecutionMode:
        """Resolve normalized execution mode for a step."""
        raw_mode = (step.input_data.get("execution_mode") or step.execution_mode or ExecutionMode.TOOL.value)
        try:
            return ExecutionMode(str(raw_mode).strip().lower())
        except ValueError:
            return ExecutionMode.TOOL

    def build_prompt_parts(
        self,
        state: WorkflowState,
        step: StepState,
        role_instruction: str,
        agent_label: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """Compose question text, session id, and system prompt override."""
        current_time = datetime.now().astimezone().isoformat(timespec="seconds")
        context = build_cumulative_context(state, step.step_id, step.input_data.get("data", {}))
        batch_summary = extract_batch_summary(context)
        task_text = str(step.input_data.get("task", ""))
        file_output_requested = task_requests_file_output(task_text)

        parts = [build_step_header_fragment(step, current_time)]
        context_fragment = build_context_fragment(context)
        if context_fragment:
            parts.append(context_fragment)
        batch_fragment = build_batch_fragment(batch_summary)
        if batch_fragment:
            parts.append(batch_fragment)
        file_fragment = build_file_output_fragment(file_output_requested)
        if file_fragment:
            parts.append(file_fragment)

        question = "\n".join(parts)
        session_id = f"wf_{state.instance_id}_{step.step_id}"
        system_extra = build_system_extra_prefix(agent_label, role_instruction, current_time, state.instance_id)
        if batch_summary:
            batch_contract = json.dumps(batch_summary.get("batch_contract") or {}, ensure_ascii=False, default=str)
            system_extra = system_extra + (
                "\n\nBatch contract: "
                + batch_contract
                + " Keep all items in scope. Continue remaining items even if one fails, and do not finish early on the first successful sample."
            )
        if file_output_requested:
            system_extra = system_extra + (
                "\n\nFile output contract: persist a real artifact in the workspace, "
                "return its saved path, and do not claim completion without a written file."
            )
        return question, session_id, system_extra

    async def run_step(
        self,
        state: WorkflowState,
        step: StepState,
        primary_skills: list[str],
        role_instruction: str,
    ) -> AgentOutput:
        mode = self.resolve_execution_mode(step)
        dispatch = {
            ExecutionMode.AGENT: self._run_agent_step,
            ExecutionMode.MULTI_AGENT: self._run_multi_agent_step,
            ExecutionMode.DISCUSSION: self._run_discussion_step,
            ExecutionMode.TOOL: self._run_tool_step,
        }
        handler = dispatch.get(mode, self._run_tool_step)
        return await handler(state, step, primary_skills, role_instruction)

    async def _run_tool_step(
        self,
        state: WorkflowState,
        step: StepState,
        primary_skills: list[str],
        role_instruction: str,
        agent_label: Optional[str] = None,
    ) -> AgentOutput:
        question, session_id, system_extra = self.build_prompt_parts(
            state,
            step,
            role_instruction,
            agent_label,
        )
        return await self._invoke_react_prompt(question, session_id, system_extra, primary_skills)

    async def _run_agent_step(
        self,
        state: WorkflowState,
        step: StepState,
        primary_skills: list[str],
        role_instruction: str,
    ) -> AgentOutput:
        agent_meta = step.input_data.get("agent_config") or {}
        agent_type = str(agent_meta.get("agent_type", step.input_data.get("role", "agent")))
        agent_role = str(agent_meta.get("role", step.input_data.get("role", "agent")))
        agent_id = f"{agent_type}_{uuid.uuid4().hex[:6]}"
        self._register_agent(state, agent_id, agent_type, agent_role, step.step_id)
        self._log_agent_message(state, agent_id, "Agent starting")
        result = await self._run_tool_step(
            state,
            step,
            primary_skills,
            role_instruction,
            agent_label=f"Agent {agent_type} ({agent_id})",
        )
        step.agent_id = agent_id
        self._log_agent_message(state, agent_id, "Agent completed")
        return result

    async def _run_multi_agent_step(
        self,
        state: WorkflowState,
        step: StepState,
        primary_skills: list[str],
        role_instruction: str,
    ) -> AgentOutput:
        config = step.input_data.get("multi_agent_config") or {}
        agents_cfg = config.get("agents") if isinstance(config, dict) else []
        if not isinstance(agents_cfg, list) or not agents_cfg:
            return await self._run_tool_step(state, step, primary_skills, role_instruction)
        collected = []
        agent_ids: list[str] = []
        for agent_cfg in agents_cfg:
            agent_type = str(agent_cfg.get("type", step.input_data.get("role", "worker")))
            agent_role = str(agent_cfg.get("role", step.input_data.get("role", "worker")))
            count = max(1, int(agent_cfg.get("count", 1)))
            for idx in range(count):
                agent_id = f"{agent_type}_{uuid.uuid4().hex[:6]}"
                self._register_agent(state, agent_id, agent_type, agent_role, step.step_id)
                self._log_agent_message(state, agent_id, f"Multi-agent member {idx + 1} running")
                result = await self._run_tool_step(
                    state,
                    step,
                    primary_skills,
                    role_instruction,
                    agent_label=f"{agent_type}-{idx + 1}",
                )
                collected.append({"agent_id": agent_id, "output": result.result})
                agent_ids.append(agent_id)
                self._log_agent_message(state, agent_id, f"Multi-agent member {idx + 1} completed")
        step.agent_ids = agent_ids
        summary = {
            "agents": collected,
            "summary": f"Multi-agent stage ran {len(agent_ids)} members",
        }
        return AgentOutput(status=AgentStatus.COMPLETED, result=summary, error=None)

    async def _run_discussion_step(
        self,
        state: WorkflowState,
        step: StepState,
        primary_skills: list[str],
        role_instruction: str,
    ) -> AgentOutput:
        discussion_config = step.input_data.get("discussion_config") or {}
        topic = discussion_config.get("topic", step.input_data.get("task", "discussion"))
        result = await self._run_multi_agent_step(state, step, primary_skills, role_instruction)
        participants = step.agent_ids or []
        thread_id = f"thread_{uuid.uuid4().hex[:8]}"
        state.add_thread(thread_id, topic, participants)
        self._log_agent_message(state, "system", f"Discussion '{topic}' concluded", thread_id)
        return result

    def _register_agent(
        self,
        state: WorkflowState,
        agent_id: str,
        agent_type: str,
        role: str,
        step_id: str,
    ) -> None:
        agent = state.agents.get(agent_id)
        if not agent:
            agent = state.add_agent(agent_id, agent_type, role, step_id)
        agent.task_count += 1
        agent.last_active = datetime.utcnow().isoformat()

    def _log_agent_message(
        self,
        state: WorkflowState,
        agent_id: str,
        text: str,
        thread_id: Optional[str] = None,
    ) -> None:
        entry = MessageEntry(
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            sender=agent_id,
            receiver=None,
            type="agent_event",
            payload={"text": text},
            thread_id=thread_id,
        )
        state.add_message(entry)
        state.add_timeline_event(
            event_type="agent_message",
            agent_id=agent_id,
            payload={"text": text, "thread_id": thread_id},
        )

    async def _invoke_react_prompt(
        self,
        question: str,
        session_id: str,
        system_extra: str,
        primary_skills: list[str],
    ) -> AgentOutput:
        provider = get_provider()
        try:
            answer, meta = await run_react(
                question=question,
                provider=provider,
                workspace_root=self._workspace_root,
                session_id=session_id,
                user_id=DEFAULT_USER_ID,
                skill_filter=None,
                fixed_selected_skills=list(primary_skills),
                context=None,
                db_path=self._db_path,
                system_prompt_override=system_extra,
                event_sink=None,
                run_id=None,
                cancel_check=None,
                decision_waiter=None,
                resume_checkpoint=None,
            )
            result = {
                "answer": answer,
                "references": meta.get("references") or [],
                "tokens": meta.get("tokens", 0),
                "role": primary_skills[0] if primary_skills else "",
            }
            if meta.get("gen_ui"):
                result["gen_ui"] = meta.get("gen_ui")
            return AgentOutput(status=AgentStatus.COMPLETED, result=result, error=None)
        except Exception as exc:
            logger.exception("Workflow step ReAct failed: %s", exc)
            return AgentOutput(status=AgentStatus.FAILED, result={}, error=str(exc))
