"""Pydantic models for HTTP request and response bodies."""

from pydantic import BaseModel

from config.defaults import DEFAULT_MODEL


# ---------------------------------------------------------------------------
# Chat models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """JSON body for ``/api/chat``, ``/api/chat/stream``, and ``/api/chat/async``.

    Attributes:
        message (str): User text for this turn.
        skill (str | None): Optional skill filter for ReAct.
        session_id (str | None): Existing session; new id generated when omitted (sync/stream).
        model (str | None): LLM id override.
        history (list[dict] | None): Deprecated; prefer DB-backed context when ``session_id`` set.
        uploaded_files (list[str] | None): Workspace paths newly uploaded for this turn.
        resume_run_id (str | None): Stream only; resume from checkpoint for this prior run.
    """

    message: str
    skill: str | None = None
    session_id: str | None = None
    model: str | None = None
    history: list[dict] | None = None
    uploaded_files: list[str] | None = None
    resume_run_id: str | None = None


class ChatResponse(BaseModel):
    """JSON body for synchronous ``POST /api/chat`` responses.

    Attributes:
        answer (str): Final assistant text.
        session_id (str): Session used for this exchange.
        cache_hit (bool): Whether a cache short-circuit applied.
        tokens (int): Total LLM tokens attributed to the run.
        gen_ui (dict | None): Optional structured UI payload from skills.
        references (list[dict] | None): Citations returned by the agent.
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
    """JSON body for ``POST /api/runs/{run_id}/decision``.

    Attributes:
        choice (str): User-selected label from the offered choices.
        choices (list[str] | None): Optional echo for validation or logging.
    """

    choice: str
    choices: list[str] | None = None


# ---------------------------------------------------------------------------
# Session models
# ---------------------------------------------------------------------------


class SessionCreateResponse(BaseModel):
    """Response for ``POST /api/sessions``.

    Attributes:
        session_id (str): New ``web-`` prefixed id.
    """

    session_id: str


class SessionListResponse(BaseModel):
    """Flat session list shape (not always wrapped by route; kept for typing).

    Attributes:
        sessions (list[dict]): Session summary dicts from the DB layer.
    """

    sessions: list[dict]


class SessionTreeResponse(BaseModel):
    """Tree session list shape for ``tree=true`` queries.

    Attributes:
        roots (list[dict]): Root sessions each with nested ``children`` metadata.
    """

    roots: list[dict]


class SessionMessagesResponse(BaseModel):
    """Messages payload for ``GET /api/sessions/{id}/messages``.

    Attributes:
        session_id (str): Resolved session id.
        messages (list[dict]): Chronological role/content rows.
        status (str | None): Async task status when ``session_meta`` exists.
    """

    session_id: str
    messages: list[dict]
    status: str | None = None


class SessionChildrenResponse(BaseModel):
    """Child rows for ``GET /api/sessions/{id}/children``.

    Attributes:
        session_id (str): Parent session id.
        children (list[dict]): Child session metadata from ``session_meta``.
    """

    session_id: str
    children: list[dict]


# ---------------------------------------------------------------------------
# Async task models
# ---------------------------------------------------------------------------


class AsyncTaskResponse(BaseModel):
    """Immediate response for ``POST /api/chat/async``.

    Attributes:
        child_session_id (str): Background session receiving the task.
        parent_session_id (str | None): Caller session when provided.
        status (str): Acceptance label (e.g. ``accepted``).
        agent (str): Agent/skill label stored on the child meta.
        kind (str): Generic label (``chat`` or ``skill``).
        run_id (str): Correlate ``TASK_*`` events on ``/api/events``.
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
    """Shape of ``GET /api/workspace/files`` JSON.

    Attributes:
        files (list[str]): Visible relative paths (recent first subset).
        recent (list[str]): Recent paths intersecting the scan.
    """

    files: list[str]
    recent: list[str]


# ---------------------------------------------------------------------------
# OpenAI-compatible models
# ---------------------------------------------------------------------------


class OpenAIModelsResponse(BaseModel):
    """Subset of OpenAI ``GET /v1/models`` list response.

    Attributes:
        object (str): Literal ``list``.
        data (list[dict]): Model id objects.
    """

    object: str = "list"
    data: list[dict]


class OpenAIChatCompletionRequest(BaseModel):
    """Documented shape for OpenAI-style chat bodies (validated loosely at route).

    Attributes:
        model (str): Model id.
        messages (list[dict]): OpenAI role/content messages.
        stream (bool): Must remain False for this server.
        session_id (str | None): Optional Sophon session binding.
    """

    model: str = DEFAULT_MODEL
    messages: list[dict]
    stream: bool = False
    session_id: str | None = None


# ---------------------------------------------------------------------------
# Admin models
# ---------------------------------------------------------------------------


class AdminActionResponse(BaseModel):
    """Generic admin action acknowledgement.

    Attributes:
        status (str): Short result code (e.g. ``ok``).
        message (str | None): Human-readable detail.
    """

    status: str
    message: str | None = None
