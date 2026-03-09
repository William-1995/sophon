"""
Chat Handler - Synchronous chat endpoint.

Non-streaming chat implementation with full ReAct loop execution.
"""

import logging

from fastapi import HTTPException

from api.models import ChatRequest, ChatResponse
from api.state import broadcast_event
from api.utils import (
    new_session_id,
    get_db_path,
    get_workspace_path,
    add_file_references_to_recent,
    build_chat_context,
)
from config import get_config
from constants import DEFAULT_USER_ID
from core.react import run_react
from db import memory_long_term
from db.logs import insert as log_insert
from providers import get_provider

logger = logging.getLogger(__name__)


async def handle_chat(req: ChatRequest) -> ChatResponse:
    """Handle synchronous chat request.

    Args:
        req: Chat request with message, optional skill/model/session.

    Returns:
        Chat response with answer and metadata.

    Raises:
        HTTPException: On processing errors.
    """
    cfg = get_config()
    ws = cfg.paths.user_workspace()
    db_path = cfg.paths.db_path()

    # Generate or use provided session ID
    session_id = req.session_id or new_session_id()

    # Get model and provider
    model = req.model or cfg.llm.default_model
    provider = get_provider(model=model)

    # Add file references to recent files
    add_file_references_to_recent(db_path, req.message)

    # Build conversation context
    context = build_chat_context(req.session_id, req.history, db_path)

    try:
        # Run ReAct loop
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

        # Extract references
        refs = meta.get("references") or []

        # Use modified_question (with @file references removed) for cleaner history
        modified_question = meta.get("modified_question", req.message)

        # Persist to database
        if db_path.exists():
            memory_long_term.insert(db_path, session_id, "user", modified_question)
            memory_long_term.insert(
                db_path, session_id, "assistant", answer,
                references=refs if refs else None,
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
        # Log error
        if db_path.exists():
            log_insert(db_path, "ERROR", f"chat_error: {e}", session_id, {"error": str(e)})

        logger.error("Chat error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
