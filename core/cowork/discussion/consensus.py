"""Consensus Checker.

Determines whether multi-Agent discussion reached consensus.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.cowork.discussion.protocol import (
    ConsensusType,
    DiscussionMessage,
    DiscussionProtocol,
    DiscussionRound,
    MessageIntent,
)


MIN_SUMMARY_LENGTH = 20
DEADLOCK_PROGRESS_THRESHOLD = 0.3
MIN_ROUNDS_FOR_PROGRESS_CHECK = 2


@dataclass
class ConsensusResult:
    """Consensus check result."""

    reached: bool
    """Whether consensus reached."""

    consensus_type: ConsensusType
    """Type of consensus reached."""

    agreement_ratio: float
    """Agreement ratio (0-1)."""

    consensus_text: Optional[str] = None
    """Consensus text (summary)."""

    dissenters: List[str] = field(default_factory=list)
    """Dissenters list (if any)."""

    abstainers: List[str] = field(default_factory=list)
    """Abstainers list (if any)."""

    def __post_init__(self):
        if self.dissenters is None:
            self.dissenters = []
        if self.abstainers is None:
            self.abstainers = []


class ConsensusChecker:
    """Consensus checker.

    Determines consensus based on discussion history.
    """

    def __init__(self, protocol: DiscussionProtocol):
        self.protocol = protocol

    def check(
        self,
        rounds: List[DiscussionRound],
        participants: List[str],
    ) -> ConsensusResult:
        if not rounds:
            return ConsensusResult(
                reached=False,
                consensus_type=self.protocol.consensus_type,
                agreement_ratio=0.0,
            )

        latest_round = rounds[-1]
        messages = latest_round.messages
        reached, ratio = self.protocol.check_consensus(messages, participants)
        positions = self._analyze_positions(messages, participants)
        consensus_text = self._extract_consensus_text(messages)

        return ConsensusResult(
            reached=reached,
            consensus_type=self.protocol.consensus_type,
            agreement_ratio=ratio,
            consensus_text=consensus_text,
            dissenters=positions.get("against", []),
            abstainers=positions.get("abstain", []),
        )

    def _analyze_positions(
        self,
        messages: List[DiscussionMessage],
        participants: List[str],
    ) -> Dict[str, List[str]]:
        positions: Dict[str, List[str]] = {
            "for": [],
            "against": [],
            "neutral": [],
            "abstain": [],
        }

        latest_positions: Dict[str, str] = {}
        for msg in messages:
            normalized = self._normalize_position(msg)
            if normalized:
                latest_positions[msg.sender_id] = normalized

        for agent_id, position in latest_positions.items():
            if position in positions:
                positions[position].append(agent_id)

        for participant in participants:
            if participant not in latest_positions:
                positions["abstain"].append(participant)

        return positions

    def _normalize_position(self, msg: DiscussionMessage) -> str | None:
        if msg.position in {"for", "against", "neutral", "abstain"}:
            return msg.position
        if msg.intent in {MessageIntent.SUPPORT, MessageIntent.PROPOSE}:
            return "for"
        if msg.intent in {MessageIntent.CHALLENGE, MessageIntent.QUESTION}:
            return "against"
        return None

    def _extract_consensus_text(self, messages: List[DiscussionMessage]) -> Optional[str]:
        for msg in reversed(messages):
            if msg.intent == MessageIntent.CONCLUDE:
                return msg.content
            if msg.intent == MessageIntent.SUMMARIZE and len(msg.content) > MIN_SUMMARY_LENGTH:
                return msg.content
        return None

    def get_discussion_summary(
        self,
        rounds: List[DiscussionRound],
    ) -> Dict[str, Any]:
        total_messages = sum(len(r.messages) for r in rounds)

        intent_counts: Dict[str, int] = {}
        for round_obj in rounds:
            for msg in round_obj.messages:
                intent = msg.intent.value
                intent_counts[intent] = intent_counts.get(intent, 0) + 1

        avg_progress = sum(r.consensus_progress for r in rounds) / len(rounds) if rounds else 0

        return {
            "total_rounds": len(rounds),
            "total_messages": total_messages,
            "intent_distribution": intent_counts,
            "average_consensus_progress": avg_progress,
            "final_round_progress": rounds[-1].consensus_progress if rounds else 0,
        }

    def suggest_next_speaker(
        self,
        rounds: List[DiscussionRound],
        participants: List[str],
        current_round: DiscussionRound,
    ) -> Optional[str]:
        spoken = set(current_round.get_participants())

        for participant in participants:
            if participant not in spoken:
                return participant

        challenge_target = self._find_challenge_target(current_round, participants)
        if challenge_target:
            return challenge_target

        return next((participant for participant in participants if "moderator" in participant.lower()), None)

    def _find_challenge_target(
        self,
        current_round: DiscussionRound,
        participants: List[str],
    ) -> Optional[str]:
        for challenge in (m for m in current_round.messages if m.is_challenge() and m.reply_to):
            original_sender = self._find_message_sender(challenge.reply_to, current_round.messages)
            if original_sender in participants:
                return original_sender
        return None

    def _find_message_sender(
        self,
        message_id: str,
        messages: List[DiscussionMessage],
    ) -> Optional[str]:
        for msg in messages:
            if msg.message_id == message_id:
                return msg.sender_id
        return None

    def should_continue(
        self,
        rounds: List[DiscussionRound],
        participants: List[str],
        max_rounds: int,
    ) -> tuple[bool, str]:
        if len(rounds) >= max_rounds:
            return False, "Reached maximum rounds limit"

        result = self.check(rounds, participants)
        if result.reached:
            return False, "Consensus already reached"

        if len(rounds) >= MIN_ROUNDS_FOR_PROGRESS_CHECK:
            latest = rounds[-1].consensus_progress
            previous = rounds[-2].consensus_progress
            if latest <= previous and latest < DEADLOCK_PROGRESS_THRESHOLD:
                return False, "Discussion deadlocked"

        return True, "Continue discussion"

    def force_consensus(
        self,
        rounds: List[DiscussionRound],
        participants: List[str],
    ) -> ConsensusResult:
        if not rounds:
            return ConsensusResult(
                reached=False,
                consensus_type=ConsensusType.DIVERGENT,
                agreement_ratio=0.0,
            )

        all_messages: List[DiscussionMessage] = []
        for round_obj in rounds:
            all_messages.extend(round_obj.messages)

        positions = self._analyze_positions(all_messages, participants)
        for_count = len(positions.get("for", []))
        against_count = len(positions.get("against", []))
        total = len(participants)
        ratio = for_count / total if total else 0.0
        reached = for_count > against_count
        consensus_text = self._extract_consensus_text(all_messages)

        return ConsensusResult(
            reached=reached,
            consensus_type=ConsensusType.MAJORITY,
            agreement_ratio=ratio,
            consensus_text=consensus_text,
            dissenters=positions.get("against", []),
            abstainers=positions.get("abstain", []),
        )
