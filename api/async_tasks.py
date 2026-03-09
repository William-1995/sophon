"""
Async Tasks - Background task handling for /api/chat/async.

Manages background task execution with status tracking and event broadcasting.
Tasks run independently and report progress via the event bus.
"""

import asyncio
import logging
import re

from fastapi import HTTPException

from api.event_types import TASK_STARTED, TASK_FINISHED, TASK_ERROR
from api.models import ChatRequest, AsyncTaskResponse
from api.state import broadcast_event
from api.utils import (
    new_session_id,
    new_run_id,
    get_db_path,
    get_workspace_path,
    add_file_references_to_recent,
    build_chat_context,
)
from config import get_config
from constants import DEFAULT_USER_ID
from core.react import run_react
from db import memory_long_term
from db import session_meta as db_session_meta
from db.logs import insert as log_insert
from providers import get_provider

logger = logging.getLogger(__name__)


async def handle_chat_async(req: ChatRequest) -> AsyncTaskResponse:
    """Submit a message as a background task.

    Returns immediately with child_session_id.
    Events streamed via GET /api/events.

    Args:
        req: Chat request with message.

    Returns:
        Task acceptance response with child session info.

    Raises:
        HTTPException: If message empty or from child session.
    """
    cfg = get_config()
    db_path = get_db_path()

    logger.info(
        "chat_async called: session_id=%s, message_len=%d",
        req.session_id,
        len(req.message) if req.message else 0,
    )

    # Validate message
    if not req.message or not req.message.strip():
        raise HTTPException(
            status_code=400,
            detail="message is required and cannot be empty",
        )

    # Only allow parent->child, not child->child (single level)
    if req.session_id and db_path.exists():
        meta = db_session_meta.get(db_path, req.session_id)
        logger.info("Session meta for %s: %s", req.session_id, meta)
        if meta and meta.get("parent_id") is not None:
            logger.warning(
                "Rejecting async from child session %s with parent %s",
                req.session_id, meta.get("parent_id"),
            )
            raise HTTPException(
                status_code=400,
                detail=f"Cannot run background task from a child session "
                       f"(parent_id={meta.get('parent_id')}). "
                       f"Switch to parent session first.",
            )

    # Create child session
    child_session_id = new_session_id()
    parent_session_id = req.session_id
    title = req.message.strip()
    agent = req.skill or "main"
    kind = _determine_task_kind(req.skill)
    run_id = new_run_id()

    # Initialize session metadata
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

    # Add file references to recent
    for match in re.finditer(r"@([^\s]+)", req.message):
        add_file_references_to_recent(db_path, match.group(1))

    # Insert placeholder in parent session
    if db_path.exists() and parent_session_id:
        memory_long_term.insert(
            db_path, parent_session_id, "user",
            f"[Background] {req.message.strip()}",
        )

    # Broadcast task started
    broadcast_event({
        "type": TASK_STARTED.value,
        "threadId": child_session_id,
        "parentThreadId": parent_session_id,
        "runId": run_id,
        "agent": agent,
        "kind": kind,
        "label": title,
    })

    # Start background task
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
) -> None:
    """Background: run ReAct for child session.

    Persists messages, updates meta, broadcasts TASK_FINISHED/TASK_ERROR.

    Args:
        child_session_id: Child session identifier.
        parent_session_id: Optional parent session identifier.
        message: User message.
        skill: Optional skill filter.
        model: Model to use.
        run_id: Run identifier.
        title: Task title.
        agent: Agent type.
        kind: Task kind.
    """
    cfg = get_config()
    db_path = get_db_path()
    ws = cfg.paths.user_workspace()
    provider = get_provider(model=model)

    # Get context from child session
    context = None
    if child_session_id and db_path.exists():
        context = memory_long_term.get_recent(
            db_path, child_session_id, limit=cfg.memory.history_recent_count
        )

    try:
        # Update status to running
        db_session_meta.update_status(db_path, child_session_id, "running")

        # Run ReAct
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

        # Extract references
        refs = meta.get("references") or []

        # Persist assistant response
        if db_path.exists():
            memory_long_term.insert(
                db_path, child_session_id, "assistant", answer,
                references=refs if refs else None,
            )

        # Update status to done
        db_session_meta.update_status(db_path, child_session_id, "done")

        # Create summary
        summary = (answer[:120] + "...") if len(answer) > 120 else answer

        # Broadcast completion
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
        # Update status to failed
        if db_path.exists():
            db_session_meta.update_status(db_path, child_session_id, "failed")
            log_insert(
                db_path, "ERROR", f"async_task_error: {e}",
                child_session_id, {"error": str(e)},
            )

        # Broadcast error
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


def _determine_task_kind(skill: str | None) -> str:
    """Determine task kind based on skill name.

    Args:
        skill: Skill name (optional).

    Returns:
        Task kind: research, crawl, or chat.
    """
    if not skill:
        return "chat"
    skill_lower = skill.lower()
    if "research" in skill_lower:
        return "research"
    if "crawler" in skill_lower:
        return "crawl"
    return "chat"
