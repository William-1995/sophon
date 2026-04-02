"""Discussion module - Multi-Agent discussion.

Provides multi-Agent discussion protocol, consensus checking, discussion coordination.
"""

from core.cowork.discussion.protocol import (
    DiscussionProtocol,
    DiscussionRound,
    DiscussionMessage,
    MessageRole,
    MessageIntent,
    ConsensusType,
)

from core.cowork.discussion.consensus import (
    ConsensusChecker,
    ConsensusResult,
)

from core.cowork.discussion.coordinator import (
    DiscussionCoordinator,
)

__all__ = [
    # Protocol
    "DiscussionProtocol",
    "DiscussionRound",
    "DiscussionMessage",
    "MessageRole",
    "MessageIntent",
    "ConsensusType",
    # Consensus
    "ConsensusChecker",
    "ConsensusResult",
    # Coordinator
    "DiscussionCoordinator",
]