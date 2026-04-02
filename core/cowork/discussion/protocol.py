"""Discussion Protocol.

Defines message format and flow for multi-Agent discussion.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


DEFAULT_MAX_MESSAGES_PER_ROUND = 10
DEFAULT_MAX_MESSAGE_LENGTH = 2000
DEFAULT_MIN_CONSENSUS_RATIO = 0.6
FREE_DISCUSSION_MESSAGE_SHARE = 3
MIN_FREE_DISCUSSION_MESSAGE_LIMIT = 1
COMPROMISE_MIN_RATIO = 0.5
DIVERGENT_CORE_RATIO = 0.5


class MessageRole(str, Enum):
    """Message roles."""

    PROPOSER = "proposer"
    """Proposer: proposes solutions or views."""

    CRITIC = "critic"
    """Critic: points out issues or raises objections."""

    SUPPORTER = "supporter"
    """Supporter: agrees and adds."""

    MODERATOR = "moderator"
    """Moderator: guides discussion, summarizes."""

    OBSERVER = "observer"
    """Observer: does not participate, only records."""


class MessageIntent(str, Enum):
    """Message intents."""

    PROPOSE = "propose"
    """Propose: "I suggest..."."""

    QUESTION = "question"
    """Question: "I have a question..."."""

    CHALLENGE = "challenge"
    """Challenge: "There's an issue here..."."""

    SUPPORT = "support"
    """Support: "I agree..."."""

    REFINE = "refine"
    """Refine: "Can be improved..."."""

    SUMMARIZE = "summarize"
    """Summarize: "The current consensus is..."."""

    CONCLUDE = "conclude"
    """Conclude: "Consensus reached..."."""


class ConsensusType(str, Enum):
    """Consensus types."""

    FULL = "full"
    """Full: all participants fully agree."""

    MAJORITY = "majority"
    """Majority: more than half agree."""

    COMPROMISE = "compromise"
    """Compromise: acceptable to all parties, not optimal."""

    DIVERGENT = "divergent"
    """Divergent: core consensus + recorded disagreements."""


@dataclass
class DiscussionMessage:
    """Discussion message.

    Richer discussion-specific message format than base Message.
    """

    message_id: str
    thread_id: str
    round_num: int

    sender_id: str
    sender_role: MessageRole

    intent: MessageIntent
    content: str

    reply_to: Optional[str] = None
    """Which message to reply to (forms conversation chain)."""

    position: Optional[str] = None
    """Position: for/against/neutral."""

    confidence: float = 1.0
    """Confidence (0-1), indicates speaker's certainty."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata, such as citations, reasoning process, etc."""

    timestamp: datetime = field(default_factory=datetime.utcnow)

    def is_consensus_related(self) -> bool:
        return self.intent in {MessageIntent.SUMMARIZE, MessageIntent.CONCLUDE}

    def is_challenge(self) -> bool:
        return self.intent in {MessageIntent.CHALLENGE, MessageIntent.QUESTION}


@dataclass
class DiscussionRound:
    """Discussion round.

    One round of discussion contains all participants' speeches.
    """

    round_num: int
    thread_id: str

    messages: List[DiscussionMessage] = field(default_factory=list)

    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    consensus_progress: float = 0.0
    """Consensus progress this round (0-1)."""

    def add_message(self, msg: DiscussionMessage) -> None:
        self.messages.append(msg)
        self._update_progress()

    def _update_progress(self) -> None:
        if not self.messages:
            return
        support_count = sum(1 for m in self.messages if m.intent == MessageIntent.SUPPORT)
        self.consensus_progress = support_count / len(self.messages)

    def complete(self) -> None:
        self.completed_at = datetime.utcnow()

    def get_participants(self) -> List[str]:
        return list(dict.fromkeys(msg.sender_id for msg in self.messages))


@dataclass
class DiscussionProtocol:
    """Discussion protocol configuration.

    Defines rules and flow of discussion.
    """

    turn_based: bool = False
    """Whether turn-based (True) or free discussion (False)."""

    max_messages_per_round: int = DEFAULT_MAX_MESSAGES_PER_ROUND
    """Maximum messages per round."""

    max_message_length: int = DEFAULT_MAX_MESSAGE_LENGTH
    """Maximum length per message."""

    assign_roles: bool = True
    """Whether to auto-assign roles."""

    require_moderator: bool = True
    """Whether moderator is required."""

    consensus_type: ConsensusType = ConsensusType.MAJORITY
    """Consensus determination method."""

    min_consensus_ratio: float = DEFAULT_MIN_CONSENSUS_RATIO
    """Minimum consensus ratio (for MAJORITY)."""

    allow_abstain: bool = True
    """Whether abstention is allowed."""

    def can_speak(self, agent_id: str, round_obj: DiscussionRound) -> bool:
        if not self.turn_based:
            agent_messages = sum(1 for m in round_obj.messages if m.sender_id == agent_id)
            return agent_messages < self._free_discussion_message_limit()
        return agent_id not in round_obj.get_participants()

    def _free_discussion_message_limit(self) -> int:
        return max(MIN_FREE_DISCUSSION_MESSAGE_LIMIT, self.max_messages_per_round // FREE_DISCUSSION_MESSAGE_SHARE)

    def check_consensus(self, messages: List[DiscussionMessage], participants: List[str]) -> tuple[bool, float]:
        if not messages or not participants:
            return False, 0.0

        positions = self._count_positions(messages)
        total_votes = len(participants)
        if total_votes == 0:
            return False, 0.0

        evaluators: Dict[ConsensusType, Callable[[Dict[str, int], int], tuple[bool, float]]] = {
            ConsensusType.FULL: self._evaluate_full_consensus,
            ConsensusType.MAJORITY: self._evaluate_majority_consensus,
            ConsensusType.COMPROMISE: self._evaluate_compromise_consensus,
            ConsensusType.DIVERGENT: self._evaluate_divergent_consensus,
        }
        evaluator = evaluators.get(self.consensus_type)
        return evaluator(positions, total_votes) if evaluator else (False, 0.0)

    def _count_positions(self, messages: List[DiscussionMessage]) -> Dict[str, int]:
        positions = {"for": 0, "against": 0, "neutral": 0, "abstain": 0}
        for msg in messages:
            position = msg.position
            if position in positions:
                positions[position] += 1
                continue
            if msg.intent in {MessageIntent.SUPPORT, MessageIntent.PROPOSE}:
                positions["for"] += 1
                continue
            if msg.intent in {MessageIntent.CHALLENGE, MessageIntent.QUESTION}:
                positions["against"] += 1
                continue
            positions["neutral"] += 1
        return positions

    def _evaluate_full_consensus(self, positions: Dict[str, int], total_votes: int) -> tuple[bool, float]:
        ratio = positions["for"] / total_votes if total_votes else 0.0
        return positions["for"] == total_votes, ratio

    def _evaluate_majority_consensus(self, positions: Dict[str, int], total_votes: int) -> tuple[bool, float]:
        ratio = positions["for"] / total_votes if total_votes else 0.0
        return ratio >= self.min_consensus_ratio, ratio

    def _evaluate_compromise_consensus(self, positions: Dict[str, int], total_votes: int) -> tuple[bool, float]:
        ratio = (positions["for"] + positions["neutral"]) / total_votes if total_votes else 0.0
        agreed = positions["against"] == 0 and ratio >= COMPROMISE_MIN_RATIO
        return agreed, ratio

    def _evaluate_divergent_consensus(self, positions: Dict[str, int], total_votes: int) -> tuple[bool, float]:
        ratio = positions["for"] / total_votes if total_votes else 0.0
        return ratio >= DIVERGENT_CORE_RATIO, ratio
