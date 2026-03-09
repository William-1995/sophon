"""
Streaming Chat - AG-UI formatted SSE streaming for /api/chat/stream.

Provides real-time streaming with progress updates, cancellation support,
and Human-in-the-Loop (HITL) decision handling.
"""

import asyncio
import logging
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from api.encoding import encode_ag_ui_event
from api.event_types import (
    RUN_STARTED,
    RUN_FINISHED,
    RUN_ERROR,
    RUN_CANCELLED,
    TEXT_MESSAGE_START,
    TEXT_MESSAGE_CONTENT,
    TEXT_MESSAGE_END,
    CUSTOM,
)
from api.models import ChatRequest
from api.state import (
    broadcast_event,
    create_cancel_event,
    cleanup_cancel_event,
    is_cancelled,
    wait_for_decision,
)
from api.utils import (
    new_session_id,
    new_run_id,
    new_message_id,
    get_db_path,
    get_workspace_path,
    add_file_references_to_recent,
    build_chat_context,
)
from config import get_config
from constants import DEFAULT_USER_ID
from core.react import run_react
from db import memory_long_term
from db import checkpoints as db_checkpoints
from db.logs import insert as log_insert
from providers import get_provider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

_DECISION_TIMEOUT = 300.0  # seconds


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_streaming_response(req: ChatRequest) -> StreamingResponse:
    """Return streaming response for chat stream endpoint.

    Args:
        req: Chat request.

    Returns:
        StreamingResponse with AG-UI formatted SSE events.
    """
    return StreamingResponse(
        _stream_chat_generator(req),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


# ---------------------------------------------------------------------------
# Private generators and helpers
# ---------------------------------------------------------------------------

async def _stream_chat_generator(req: ChatRequest):
    """Generate AG-UI formatted SSE events for chat stream.

    Handles:
    - Resume from checkpoint if resume_run_id provided
    - Progress updates via queue
    - Event emission via queue
    - Cancellation support
    - HITL decision handling
    - Result persistence

    Args:
        req: Chat request.

    Yields:
        SSE formatted event strings.
    """
    cfg = get_config()
    ws = cfg.paths.user_workspace()
    db_path = get_db_path()

    # Initialize session and run
    session_id = req.session_id or new_session_id()
    run_id = new_run_id()
    msg_id = new_message_id()
    model = req.model or cfg.llm.default_model
    provider = get_provider(model=model)

    # Handle resume from checkpoint
    resume_checkpoint = _load_checkpoint(db_path, req.resume_run_id, run_id)
    if resume_checkpoint is None and req.resume_run_id:
        # Checkpoint not found error
        yield encode_ag_ui_event({
            "type": RUN_ERROR.value,
            "message": f"Checkpoint not found for run_id={req.resume_run_id}",
        })
        return

    # Determine question (from checkpoint or request)
    question = _determine_question(req.message, resume_checkpoint)

    # Add file references to recent
    add_file_references_to_recent(db_path, req.message)

    # Build context
    context = build_chat_context(req.session_id, req.history, db_path)

    # Setup event queue and callbacks
    queue: asyncio.Queue = asyncio.Queue()

    def on_progress(tokens: int, round_num: int | None):
        """Callback for progress updates."""
        queue.put_nowait({
            "type": CUSTOM.value,
            "name": "progress",
            "value": {"tokens": tokens, "round": round_num},
        })

    def on_event(evt: dict):
        """Callback for tool events."""
        queue.put_nowait({"type": CUSTOM.value, "name": "sophon_event", "value": evt})

    # Setup cancellation
    create_cancel_event(run_id)

    def cancel_check() -> bool:
        """Check if run has been cancelled."""
        return is_cancelled(run_id)

    # Setup HITL decision handler
    async def decision_handler(message: str, choices: list[str]) -> str:
        """Handle HITL decision request."""
        return await wait_for_decision(run_id, message, choices)

    # Start background task
    task = asyncio.create_task(_run_chat_task(
        queue=queue,
        question=question,
        provider=provider,
        workspace_root=ws,
        session_id=session_id,
        skill=req.skill,
        context=context,
        db_path=db_path,
        progress_callback=on_progress,
        event_callback=on_event,
        run_id=run_id,
        cancel_check=cancel_check,
        decision_waiter=decision_handler,
        resume_checkpoint=resume_checkpoint,
        req_message=req.message,
        msg_id=msg_id,
    ))

    # Emit RUN_STARTED immediately
    yield encode_ag_ui_event({
        "type": RUN_STARTED.value,
        "threadId": session_id,
        "runId": run_id,
    })

    # Stream events from queue
    try:
        while True:
            item = await queue.get()
            if item is None:
                # Task complete
                break
            yield encode_ag_ui_event(item)
    finally:
        # Check for any exception
        try:
            exc = task.exception() if task.done() else None
            if exc:
                yield encode_ag_ui_event({
                    "type": RUN_ERROR.value,
                    "message": str(exc),
                })
        except (asyncio.InvalidStateError, asyncio.CancelledError):
            pass

        # Cleanup
        cleanup_cancel_event(run_id)


async def _run_chat_task(
    queue: asyncio.Queue,
    question: str,
    provider,
    workspace_root: Path,
    session_id: str,
    skill: str | None,
    context: list[dict],
    db_path: Path,
    progress_callback,
    event_callback,
    run_id: str,
    cancel_check,
    decision_waiter,
    resume_checkpoint: dict | None,
    req_message: str,
    msg_id: str,
) -> None:
    """Background task to run ReAct and emit events.

    Args:
        queue: Event queue for streaming.
        question: Question to process.
        provider: LLM provider.
        workspace_root: Workspace path.
        session_id: Session ID.
        skill: Optional skill filter.
        context: Conversation context.
        db_path: Database path.
        progress_callback: Progress callback.
        event_callback: Event callback.
        run_id: Run ID.
        cancel_check: Cancellation check.
        decision_waiter: HITL decision handler.
        resume_checkpoint: Optional checkpoint.
        req_message: Original request message.
        msg_id: Message ID.
    """
    try:
        # Run ReAct loop
        answer, meta = await run_react(
            question=question,
            provider=provider,
            workspace_root=workspace_root,
            session_id=session_id,
            user_id=DEFAULT_USER_ID,
            skill_filter=skill,
            context=context if context else None,
            db_path=db_path,
            progress_callback=progress_callback,
            event_sink=event_callback,
            run_id=run_id,
            cancel_check=cancel_check,
            decision_waiter=decision_waiter,
            resume_checkpoint=resume_checkpoint,
        )

        refs = meta.get("references") or []

        # Handle cancellation
        if meta.get("cancelled"):
            queue.put_nowait({
                "type": RUN_CANCELLED.value,
                "threadId": session_id,
                "runId": run_id,
            })

        # Persist to database
        if db_path.exists() and not meta.get("cancelled"):
            memory_long_term.insert(db_path, session_id, "user", req_message)
            memory_long_term.insert(
                db_path, session_id, "assistant", answer,
                references=refs if refs else None,
            )

        # Emit text message
        queue.put_nowait({
            "type": TEXT_MESSAGE_START.value,
            "messageId": msg_id,
            "role": "assistant",
        })
        queue.put_nowait({
            "type": TEXT_MESSAGE_CONTENT.value,
            "messageId": msg_id,
            "delta": answer,
        })
        queue.put_nowait({
            "type": TEXT_MESSAGE_END.value,
            "messageId": msg_id,
        })

        # Emit gen_ui if present
        gen_ui = meta.get("gen_ui")
        if gen_ui:
            queue.put_nowait({
                "type": CUSTOM.value,
                "name": "gen_ui",
                "value": gen_ui,
            })

        # Build result payload
        result_payload: dict = {
            "session_id": session_id,
            "tokens": meta.get("tokens", 0),
            "cache_hit": meta.get("cache_hit", False),
            "gen_ui": gen_ui,
            "cancelled": meta.get("cancelled", False),
        }
        if refs:
            result_payload["references"] = refs

        # Emit completion
        queue.put_nowait({
            "type": RUN_FINISHED.value,
            "threadId": session_id,
            "runId": run_id,
            "result": result_payload,
        })

    except Exception as e:
        # Log error
        if db_path.exists():
            log_insert(
                db_path, "ERROR", f"chat_error: {e}",
                session_id, {"error": str(e)},
            )

        # Emit error
        queue.put_nowait({"type": RUN_ERROR.value, "message": str(e)})

    finally:
        # Signal completion
        queue.put_nowait(None)


def _load_checkpoint(
    db_path: Path,
    resume_run_id: str | None,
    current_run_id: str,
) -> dict | None:
    """Load checkpoint if resume_run_id is provided.

    Args:
        db_path: Database path.
        resume_run_id: Run ID to resume from.
        current_run_id: Current run ID (for error messages).

    Returns:
        Checkpoint dict or None.
    """
    if not resume_run_id or not db_path.exists():
        return None

    cp = db_checkpoints.get_by_run_id(db_path, resume_run_id)
    return cp


def _determine_question(message: str, resume_checkpoint: dict | None) -> str:
    """Determine the question to use.

    Args:
        message: Request message.
        resume_checkpoint: Optional checkpoint.

    Returns:
        Question string.
    """
    if resume_checkpoint and resume_checkpoint.get("question"):
        return str(resume_checkpoint["question"])
    return message
