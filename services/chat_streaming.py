"""SSE streaming chat for ``POST /api/chat/stream`` (AG-UI events)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi.responses import StreamingResponse

from common.encoding import encode_ag_ui_event
from common.utils import get_db_path, new_message_id, new_run_id, new_session_id
from services.chat_context import build_chat_context
from services.recent_files import add_file_references_to_recent
from api.schemas.event_types import (
    CUSTOM,
    DECISION_REQUIRED,
    RUN_CANCELLED,
    RUN_ERROR,
    RUN_FINISHED,
    RUN_STARTED,
    TEXT_MESSAGE_CONTENT,
    TEXT_MESSAGE_END,
    TEXT_MESSAGE_START,
)
from api.schemas.models import ChatRequest
from config import get_config
from constants import DEFAULT_USER_ID
from core.react import run_react
from db import checkpoints as db_checkpoints
from db import memory_long_term
from db.logs import insert as log_insert
from providers import get_provider
from services.state import (
    cleanup_cancel_event,
    create_cancel_event,
    is_cancelled,
    wait_for_decision,
)

logger = logging.getLogger(__name__)

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def get_streaming_response(req: ChatRequest) -> StreamingResponse:
    """Return an SSE response that drives one streamed ReAct run.

    Args:
        req (ChatRequest): User message, session, skill, optional ``resume_run_id``.

    Returns:
        ``StreamingResponse`` with ``text/event-stream`` and no-buffer headers.
    """
    return StreamingResponse(
        _stream_chat_generator(req),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


async def _stream_chat_generator(req: ChatRequest):
    """Yield encoded SSE lines for run lifecycle, tool events, text deltas, and HITL.

    Args:
        req (ChatRequest): Same payload as ``get_streaming_response``.

    Yields:
        ``str``: SSE lines from ``encode_ag_ui_event`` (including errors).
    """
    cfg = get_config()
    ws = cfg.paths.user_workspace()
    db_path = get_db_path()

    session_id = req.session_id or new_session_id()
    run_id = new_run_id()
    msg_id = new_message_id()
    model = req.model or cfg.llm.default_model
    provider = get_provider(model=model)

    resume_checkpoint = _load_checkpoint(db_path, req.resume_run_id, run_id)
    if resume_checkpoint is None and req.resume_run_id:
        yield encode_ag_ui_event({
            "type": RUN_ERROR.value,
            "message": f"Checkpoint not found for run_id={req.resume_run_id}",
        })
        return

    question = _determine_question(req.message, resume_checkpoint)

    add_file_references_to_recent(db_path, req.message)
    context = build_chat_context(req.session_id, req.history, db_path, req.uploaded_files)

    queue: asyncio.Queue = asyncio.Queue()

    def on_progress(tokens: int, round_num: int | None):
        queue.put_nowait({
            "type": CUSTOM.value,
            "name": "progress",
            "value": {"tokens": tokens, "round": round_num},
        })

    def on_event(evt: dict):
        queue.put_nowait({"type": CUSTOM.value, "name": "sophon_event", "value": evt})

    create_cancel_event(run_id)

    def cancel_check() -> bool:
        return is_cancelled(run_id)

    async def decision_handler(message: str, choices: list[str], *, payload: dict | None = None) -> str:
        logger.info("[hitl] decision_handler run_id=%s choices=%s", run_id, choices)
        event = {
            "type": DECISION_REQUIRED.value,
            "runId": run_id,
            "message": message,
            "choices": choices,
        }
        if payload:
            event["payload"] = payload
        try:
            queue.put_nowait(event)
        except Exception as e:
            logger.warning("[streaming] failed to put DECISION_REQUIRED in queue: %s", e)
        return await wait_for_decision(run_id, message, choices, payload=payload)

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

    yield encode_ag_ui_event({
        "type": RUN_STARTED.value,
        "threadId": session_id,
        "runId": run_id,
    })

    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield encode_ag_ui_event(item)
    finally:
        try:
            exc = task.exception() if task.done() else None
            if exc:
                yield encode_ag_ui_event({"type": RUN_ERROR.value, "message": str(exc)})
        except (asyncio.InvalidStateError, asyncio.CancelledError):
            pass

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
    """Run ``run_react`` and enqueue AG-UI text + completion events.

    On success, inserts memory rows (unless cancelled) and pushes
    ``TEXT_MESSAGE_*`` and ``RUN_FINISHED`` (or ``RUN_CANCELLED``) to ``queue``.
    On failure, pushes ``RUN_ERROR`` and logs when the DB exists.

    Args:
        queue (asyncio.Queue): Mixed event dicts and terminal ``None`` sentinel.
        question (str): Resolved user question (may come from checkpoint resume).
        provider: LLM provider instance.
        workspace_root (Path): User workspace root.
        session_id (str): Conversation session.
        skill (str | None): ReAct skill filter.
        context (list[dict]): Prior turns for the model.
        db_path (Path): SQLite path.
        progress_callback: Token/round progress hook for ReAct.
        event_callback: Arbitrary event sink for ReAct.
        run_id (str): Correlates cancel and HITL.
        cancel_check: Callable returning whether the run should stop.
        decision_waiter: Async HITL handler passed to ReAct.
        resume_checkpoint (dict | None): Optional checkpoint for resumable runs.
        req_message (str): Original user message text for persistence.
        msg_id (str): AG-UI assistant message id.
    """
    try:
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
        if meta.get("cancelled"):
            queue.put_nowait({
                "type": RUN_CANCELLED.value,
                "threadId": session_id,
                "runId": run_id,
            })

        if db_path.exists() and not meta.get("cancelled"):
            memory_long_term.insert(db_path, session_id, "user", req_message)
            memory_long_term.insert(
                db_path, session_id, "assistant", answer,
                references=refs if refs else None,
            )
            from services.emotion import enqueue_segment_analysis
            enqueue_segment_analysis(
                db_path=db_path,
                session_id=session_id,
                user_message=req_message,
                assistant_message=answer,
            )

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

        gen_ui = meta.get("gen_ui")
        if gen_ui:
            queue.put_nowait({
                "type": CUSTOM.value,
                "name": "gen_ui",
                "value": gen_ui,
            })

        result_payload: dict = {
            "session_id": session_id,
            "tokens": meta.get("tokens", 0),
            "cache_hit": meta.get("cache_hit", False),
            "gen_ui": gen_ui,
            "cancelled": meta.get("cancelled", False),
            "resumable": meta.get("resumable", False),
        }
        if refs:
            result_payload["references"] = refs

        queue.put_nowait({
            "type": RUN_FINISHED.value,
            "threadId": session_id,
            "runId": run_id,
            "result": result_payload,
        })
    except Exception as e:
        if db_path.exists():
            log_insert(
                db_path, "ERROR", f"chat_error: {e}",
                session_id, {"error": str(e)},
            )

        queue.put_nowait({"type": RUN_ERROR.value, "message": str(e)})
    finally:
        queue.put_nowait(None)


def _load_checkpoint(db_path: Path, resume_run_id: str | None, current_run_id: str) -> dict | None:
    """Load a resumable checkpoint when ``resume_run_id`` is set.

    Args:
        db_path (Path): SQLite path.
        resume_run_id (str | None): Prior run to resume.
        current_run_id (str): Unused; reserved for future correlation.

    Returns:
        Checkpoint dict or ``None``.
    """
    if not resume_run_id or not db_path.exists():
        return None
    return db_checkpoints.get_by_run_id(db_path, resume_run_id)


def _determine_question(message: str, resume_checkpoint: dict | None) -> str:
    """Use checkpoint question when resuming; otherwise the live message.

    Args:
        message (str): Incoming request text.
        resume_checkpoint (dict | None): Optional stored ReAct state.

    Returns:
        Question string passed to ``run_react``.
    """
    if resume_checkpoint and resume_checkpoint.get("question"):
        return str(resume_checkpoint["question"])
    return message
