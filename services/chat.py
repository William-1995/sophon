"""Synchronous chat: one full ReAct run and a JSON ``ChatResponse``."""

from __future__ import annotations

import logging

from fastapi import HTTPException

from common.utils import new_session_id
from services.chat_context import build_chat_context
from services.recent_files import add_file_references_to_recent
from api.schemas.models import ChatRequest, ChatResponse
from config import get_config
from constants import DEFAULT_USER_ID
from core.react import run_react
from db import memory_long_term
from db.logs import insert as log_insert
from providers import get_provider
from services.emotion import enqueue_segment_analysis

logger = logging.getLogger(__name__)


async def handle_chat(req: ChatRequest) -> ChatResponse:
    """Execute ReAct once, persist memory, and return the assistant answer.

    Args:
        req (ChatRequest): User message, optional session, skill filter, model, history.

    Returns:
        ``ChatResponse`` with answer, session id, token count, optional UI payload.

    Raises:
        HTTPException: 500 on unhandled errors (also logs to DB when possible).
    """
    cfg = get_config()
    ws = cfg.paths.user_workspace()
    db_path = cfg.paths.db_path()

    session_id = req.session_id or new_session_id()
    model = req.model or cfg.llm.default_model
    provider = get_provider(model=model)

    add_file_references_to_recent(db_path, req.message)
    context = build_chat_context(req.session_id, req.history, db_path, req.uploaded_files)

    try:
        answer, meta = await run_react(
            question=req.message,
            provider=provider,
            workspace_root=ws,
            session_id=session_id,
            user_id=DEFAULT_USER_ID,
            skill_filter=req.skill,
            context=context if context else None,
            db_path=db_path,
        )

        refs = meta.get("references") or []
        modified_question = meta.get("modified_question", req.message)

        if db_path.exists():
            memory_long_term.insert(db_path, session_id, "user", modified_question)
            memory_long_term.insert(
                db_path, session_id, "assistant", answer,
                references=refs if refs else None,
            )
            enqueue_segment_analysis(
                db_path=db_path,
                session_id=session_id,
                user_message=modified_question,
                assistant_message=answer,
            )

        return ChatResponse(
            answer=answer,
            session_id=session_id,
            cache_hit=meta.get("cache_hit", False),
            tokens=meta.get("tokens", 0),
            gen_ui=meta.get("gen_ui"),
            references=refs if refs else None,
        )
    except Exception as e:
        if db_path.exists():
            log_insert(db_path, "ERROR", f"chat_error: {e}", session_id, {"error": str(e)})
        logger.error("Chat error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
