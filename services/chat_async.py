"""Background chat for ``POST /api/chat/async`` (child session + SSE lifecycle)."""

from __future__ import annotations

import asyncio
import logging
import re

from fastapi import HTTPException

from common.utils import get_db_path, new_run_id, new_session_id
from services.chat_context import build_uploaded_files_context
from services.recent_files import add_file_references_to_recent
from api.schemas.event_types import TASK_ERROR, TASK_FINISHED, TASK_STARTED
from api.schemas.models import AsyncTaskResponse, ChatRequest
from config import get_config
from constants import ASYNC_TASK_ANSWER_SUMMARY_MAX, DEFAULT_USER_ID
from core.react import run_react
from db import memory_long_term
from db import session_meta as db_session_meta
from db.logs import insert as log_insert
from providers import get_provider
from services.state import broadcast_event

logger = logging.getLogger(__name__)


async def handle_chat_async(req: ChatRequest) -> AsyncTaskResponse:
    """Queue a ReAct run on a new child session and return ids immediately.

    Args:
        req (ChatRequest): Must include a non-empty ``message``.

    Returns:
        ``AsyncTaskResponse`` with child/parent session ids, run id, and metadata.

    Raises:
        HTTPException: 400 for empty message or async from a child session.
    """
    cfg = get_config()
    db_path = get_db_path()

    logger.info(
        "chat_async called: session_id=%s, message_len=%d",
        req.session_id,
        len(req.message) if req.message else 0,
    )

    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="message is required and cannot be empty")

    if req.session_id and db_path.exists():
        meta = db_session_meta.get(db_path, req.session_id)
        logger.info("Session meta for %s: %s", req.session_id, meta)
        if meta and meta.get("parent_id") is not None:
            logger.warning(
                "Rejecting async from child session %s with parent %s",
                req.session_id,
                meta.get("parent_id"),
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot run background task from a child session "
                    f"(parent_id={meta.get('parent_id')}). "
                    f"Switch to parent session first."
                ),
            )

    child_session_id = new_session_id()
    parent_session_id = req.session_id
    title = req.message.strip()
    agent = req.skill or "main"
    kind = "skill" if req.skill else "chat"
    run_id = new_run_id()

    if db_path.exists():
        db_session_meta.upsert(
            db_path,
            child_session_id,
            parent_id=parent_session_id,
            title=title,
            agent=agent,
            kind=kind,
            status="queued",
        )
        memory_long_term.insert(db_path, child_session_id, "user", req.message.strip())

    for match in re.finditer(r"@([^\s]+)", req.message):
        add_file_references_to_recent(db_path, match.group(1))

    if db_path.exists() and parent_session_id:
        memory_long_term.insert(
            db_path, parent_session_id, "user", f"[Background] {req.message.strip()}",
        )

    broadcast_event({
        "type": TASK_STARTED.value,
        "threadId": child_session_id,
        "parentThreadId": parent_session_id,
        "runId": run_id,
        "agent": agent,
        "kind": kind,
        "label": title,
    })

    asyncio.create_task(_run_async_task(
        child_session_id=child_session_id,
        parent_session_id=parent_session_id,
        message=req.message,
        skill=req.skill,
        model=req.model or cfg.llm.default_model,
        run_id=run_id,
        title=title,
        agent=agent,
        kind=kind,
        uploaded_files=req.uploaded_files,
    ))

    return AsyncTaskResponse(
        child_session_id=child_session_id,
        parent_session_id=parent_session_id,
        status="accepted",
        agent=agent,
        kind=kind,
        run_id=run_id,
    )


async def _run_async_task(
    child_session_id: str,
    parent_session_id: str | None,
    message: str,
    skill: str | None,
    model: str,
    run_id: str,
    title: str,
    agent: str,
    kind: str,
    uploaded_files: list[str] | None = None,
) -> None:
    """Run ``run_react`` for the child session; broadcast finish or error.

    Args:
        child_session_id (str): Background run session.
        parent_session_id (str | None): Original thread id, if any.
        message (str): User text.
        skill (str | None): Skill filter for ReAct.
        model (str): Resolved model id.
        run_id (str): Correlates SSE events.
        title (str): Task label (trimmed user message).
        agent (str): Agent label (skill or ``main``).
        kind (str): Generic task kind label (``chat`` or ``skill``).
    """
    cfg = get_config()
    db_path = get_db_path()
    ws = cfg.paths.user_workspace()
    provider = get_provider(model=model)

    context = build_uploaded_files_context(uploaded_files)
    if child_session_id and db_path.exists():
        context.extend(
            memory_long_term.get_recent(
                db_path, child_session_id, limit=cfg.memory.history_recent_count
            )
        )

    try:
        db_session_meta.update_status(db_path, child_session_id, "running")

        answer, meta = await run_react(
            question=message,
            provider=provider,
            workspace_root=ws,
            session_id=child_session_id,
            user_id=DEFAULT_USER_ID,
            skill_filter=skill,
            context=context if context else None,
            db_path=db_path,
        )

        refs = meta.get("references") or []

        if db_path.exists():
            memory_long_term.insert(
                db_path, child_session_id, "assistant", answer,
                references=refs if refs else None,
            )

        db_session_meta.update_status(db_path, child_session_id, "done")

        summary = (
            (answer[:ASYNC_TASK_ANSWER_SUMMARY_MAX] + "...")
            if len(answer) > ASYNC_TASK_ANSWER_SUMMARY_MAX
            else answer
        )

        broadcast_event({
            "type": TASK_FINISHED.value,
            "threadId": child_session_id,
            "parentThreadId": parent_session_id,
            "runId": run_id,
            "agent": agent,
            "kind": kind,
            "label": title,
            "result": {
                "session_id": child_session_id,
                "tokens": meta.get("tokens", 0),
                "summary": summary,
            },
        })
    except Exception as e:
        if db_path.exists():
            db_session_meta.update_status(db_path, child_session_id, "failed")
            log_insert(
                db_path, "ERROR", f"async_task_error: {e}",
                child_session_id, {"error": str(e)},
            )

        broadcast_event({
            "type": TASK_ERROR.value,
            "threadId": child_session_id,
            "parentThreadId": parent_session_id,
            "runId": run_id,
            "agent": agent,
            "kind": kind,
            "label": title,
            "message": str(e),
        })
