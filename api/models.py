"""
API Models - Pydantic models for request/response validation.

All API input/output schemas are defined here for type safety and validation.
"""

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Chat models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Request model for chat endpoints.

    Attributes:
        message: User's message/question.
        skill: Optional skill to use for this request.
        session_id: Optional session identifier (creates new if not provided).
        model: Optional model override (e.g., qwen-mlx, deepseek-chat).
        history: Deprecated - backend uses DB when session_id is set.
        resume_run_id: Optional run_id to resume from checkpoint.
    """

    message: str
    skill: str | None = None
    session_id: str | None = None
    model: str | None = None
    history: list[dict] | None = None
    resume_run_id: str | None = None


class ChatResponse(BaseModel):
    """Response model for chat endpoints.

    Attributes:
        answer: Assistant's response text.
        session_id: Session identifier.
        cache_hit: Whether response was served from cache.
        tokens: Total tokens used in this conversation.
        gen_ui: Optional UI generation data.
        references: Optional list of reference sources.
    """

    answer: str
    session_id: str
    cache_hit: bool = False
    tokens: int = 0
    gen_ui: dict | None = None
    references: list[dict] | None = None


# ---------------------------------------------------------------------------
# HITL models
# ---------------------------------------------------------------------------

class DecisionRequest(BaseModel):
    """Request model for HITL decision submission.

    Attributes:
        choice: User's selected choice.
        choices: Optional list of available choices (for validation).
    """

    choice: str
    choices: list[str] | None = None


# ---------------------------------------------------------------------------
# Session models
# ---------------------------------------------------------------------------

class SessionCreateResponse(BaseModel):
    """Response model for session creation.

    Attributes:
        session_id: Newly created session identifier.
    """

    session_id: str


class SessionListResponse(BaseModel):
    """Response model for session listing.

    Attributes:
        sessions: List of session summaries.
    """

    sessions: list[dict]


class SessionTreeResponse(BaseModel):
    """Response model for session tree listing.

    Attributes:
        roots: List of root sessions with their children.
    """

    roots: list[dict]


class SessionMessagesResponse(BaseModel):
    """Response model for session messages.

    Attributes:
        session_id: Session identifier.
        messages: List of messages in the session.
        status: Optional session status (for async tasks).
    """

    session_id: str
    messages: list[dict]
    status: str | None = None


class SessionChildrenResponse(BaseModel):
    """Response model for session children.

    Attributes:
        session_id: Parent session identifier.
        children: List of child sessions.
    """

    session_id: str
    children: list[dict]


# ---------------------------------------------------------------------------
# Async task models
# ---------------------------------------------------------------------------

class AsyncTaskResponse(BaseModel):
    """Response model for async task submission.

    Attributes:
        child_session_id: Created child session identifier.
        parent_session_id: Parent session identifier (if any).
        status: Task acceptance status.
        agent: Agent type handling the task.
        kind: Task kind (research, crawl, chat).
        run_id: Run identifier for tracking.
    """

    child_session_id: str
    parent_session_id: str | None
    status: str
    agent: str
    kind: str
    run_id: str


# ---------------------------------------------------------------------------
# Workspace models
# ---------------------------------------------------------------------------

class WorkspaceFilesResponse(BaseModel):
    """Response model for workspace files listing.

    Attributes:
        files: List of file paths.
        recent: List of recently accessed files.
    """

    files: list[str]
    recent: list[str]


# ---------------------------------------------------------------------------
# OpenAI-compatible models
# ---------------------------------------------------------------------------

class OpenAIModelsResponse(BaseModel):
    """OpenAI-compatible /v1/models response.

    Attributes:
        object: Object type (always "list").
        data: List of available models.
    """

    object: str = "list"
    data: list[dict]


class OpenAIChatCompletionRequest(BaseModel):
    """OpenAI-compatible /v1/chat/completions request.

    Attributes:
        model: Model identifier.
        messages: List of conversation messages.
        stream: Whether to stream response (must be False).
        session_id: Optional session identifier.
    """

    model: str = "deepseek-chat"
    messages: list[dict]
    stream: bool = False
    session_id: str | None = None


# ---------------------------------------------------------------------------
# Admin models
# ---------------------------------------------------------------------------

class AdminActionResponse(BaseModel):
    """Response model for admin actions.

    Attributes:
        status: Action status.
        message: Optional status message.
    """

    status: str
    message: str | None = None
