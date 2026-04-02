"""Discussion Coordinator.

Manages complete multi-Agent discussion flow: creation, progression, convergence.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, List, Optional

from core.cowork import AgentRuntime
from core.cowork.workflow.state import MessageEntry, ThreadState, WorkflowState
from core.cowork.discussion.protocol import (
    DiscussionMessage,
    DiscussionProtocol,
    DiscussionRound,
    MessageIntent,
    MessageRole,
)
from core.cowork.discussion.consensus import ConsensusChecker, ConsensusResult

DEFAULT_MAX_ROUNDS = 3
MODERATOR_INDEX = 0
RECENT_PROMPT_MESSAGE_COUNT = 3
MESSAGE_PREVIEW_CHARS = 100
ID_SUFFIX_CHARS = 8


class DiscussionCoordinator:
    """Discussion coordinator.

    Responsible for coordinating multi-Agent discussion process until consensus or timeout.
    """

    def __init__(
        self,
        runtime: AgentRuntime,
        protocol: Optional[DiscussionProtocol] = None,
    ):
        self.runtime = runtime
        self.protocol = protocol or DiscussionProtocol()
        self.consensus_checker = ConsensusChecker(self.protocol)

    async def coordinate(
        self,
        workflow_state: WorkflowState,
        topic: str,
        participant_types: List[str],
        max_rounds: int = DEFAULT_MAX_ROUNDS,
        on_round_complete: Optional[Callable[[int, ConsensusResult], None]] = None,
    ) -> ConsensusResult:
        """Coordinate discussion until consensus reached."""
        thread_id = f"thread_{uuid.uuid4().hex[:ID_SUFFIX_CHARS]}"

        participants = await self._create_participants(participant_types, workflow_state.instance_id)
        thread = workflow_state.add_thread(thread_id, topic, participants)
        rounds: List[DiscussionRound] = []

        for round_num in range(1, max_rounds + 1):
            current_round = DiscussionRound(round_num=round_num, thread_id=thread_id)
            rounds.append(current_round)

            await self._conduct_round(
                round_num=round_num,
                thread_id=thread_id,
                topic=topic,
                participants=participants,
                workflow_state=workflow_state,
                current_round=current_round,
            )
            current_round.complete()

            consensus = self.consensus_checker.check(rounds, participants)
            if on_round_complete:
                on_round_complete(round_num, consensus)

            if consensus.reached:
                thread.consensus_reached = True
                thread.consensus_result = {
                    "text": consensus.consensus_text,
                    "agreement_ratio": consensus.agreement_ratio,
                    "type": consensus.consensus_type.value,
                }
                break

            should_continue, _ = self.consensus_checker.should_continue(rounds, participants, max_rounds)
            if not should_continue:
                break

        await self._cleanup_participants(participants)

        if not thread.consensus_reached:
            consensus = self.consensus_checker.force_consensus(rounds, participants)
            thread.consensus_reached = consensus.reached
            thread.consensus_result = {
                "text": consensus.consensus_text or f"Discussion ended ({max_rounds} rounds), consensus not fully reached",
                "agreement_ratio": consensus.agreement_ratio,
                "type": "forced",
            }

        return consensus

    async def _create_participants(self, participant_types: List[str], instance_id: str) -> List[str]:
        participants: List[str] = []
        for i, agent_type in enumerate(participant_types):
            role = "moderator" if i == MODERATOR_INDEX and self.protocol.require_moderator else "discussant"
            agent_id = await self.runtime.spawn(agent_type=agent_type, role=role, instance_id=instance_id)
            participants.append(agent_id)
        return participants

    async def _cleanup_participants(self, participants: List[str]) -> None:
        for agent_id in participants:
            await self.runtime.kill(agent_id)

    async def _conduct_round(
        self,
        round_num: int,
        thread_id: str,
        topic: str,
        participants: List[str],
        workflow_state: WorkflowState,
        current_round: DiscussionRound,
    ) -> None:
        for i, agent_id in enumerate(participants):
            if not self.protocol.can_speak(agent_id, current_round):
                continue

            prompt = self._build_prompt(
                topic=topic,
                round_num=round_num,
                agent_index=i,
                previous_messages=current_round.messages,
            )

            result = await self.runtime.invoke(agent_id, {"discussion_prompt": prompt})
            if not (result.success and result.output):
                continue

            content = result.output.get("message", "")
            intent_str = result.output.get("intent", "propose")
            position = result.output.get("position", "neutral")

            msg = DiscussionMessage(
                message_id=f"msg_{uuid.uuid4().hex[:ID_SUFFIX_CHARS]}",
                thread_id=thread_id,
                round_num=round_num,
                sender_id=agent_id,
                sender_role=MessageRole.MODERATOR if i == MODERATOR_INDEX else MessageRole.PROPOSER,
                intent=MessageIntent(intent_str),
                content=content,
                position=position,
            )
            current_round.add_message(msg)

            workflow_state.add_message(
                MessageEntry(
                    message_id=msg.message_id,
                    sender=agent_id,
                    receiver=None,
                    type=f"discussion_{intent_str}",
                    payload={
                        "content": content,
                        "round": round_num,
                        "position": position,
                    },
                    timestamp=msg.timestamp,
                    thread_id=thread_id,
                )
            )

    def _build_prompt(
        self,
        topic: str,
        round_num: int,
        agent_index: int,
        previous_messages: List[DiscussionMessage],
    ) -> str:
        prompt_parts = [f"Discussion topic: {topic}", f"Current round: Round {round_num}"]

        if agent_index == MODERATOR_INDEX:
            prompt_parts.append("You are the moderator, please guide the discussion or summarize current views.")
        else:
            prompt_parts.append("Please share your views on the topic.")

        if previous_messages:
            prompt_parts.append("\nPrevious views:")
            for msg in previous_messages[-RECENT_PROMPT_MESSAGE_COUNT:]:
                prompt_parts.append(f"- {msg.sender_id}: {msg.content[:MESSAGE_PREVIEW_CHARS]}...")

        prompt_parts.extend(
            [
                "\nPlease reply in JSON format:",
                "{",
                '  "intent": "propose|support|challenge|summarize",',
                '  "position": "for|against|neutral",',
                '  "message": "your message content"',
                "}",
            ]
        )
        return "\n".join(prompt_parts)

    def get_discussion_report(self, thread: ThreadState) -> Dict[str, Any]:
        return {
            "thread_id": thread.thread_id,
            "topic": thread.topic,
            "participants": thread.participant_ids,
            "total_messages": len(thread.messages),
            "consensus_reached": thread.consensus_reached,
            "consensus": thread.consensus_result,
            "duration_minutes": (
                (thread.completed_at - thread.started_at).total_seconds() / 60 if thread.completed_at else None
            ),
        }
