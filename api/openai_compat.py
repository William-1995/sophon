"""
OpenAI-compatible API - /v1/models and /v1/chat/completions endpoints.

Provides OpenAI API compatibility for integration with OpenAI-compatible clients.
Note: stream=true is not supported (returns 400 error).
"""

import time
from pathlib import Path

from fastapi import Body, HTTPException

from api.models import ChatRequest, ChatResponse
from api.utils import (
    new_session_id,
    parse_messages,
    get_db_path,
    get_workspace_path,
    add_file_references_to_recent,
    build_chat_context,
)
from config import get_config
from core.react import run_react
from db import memory_long_term
from constants import DEFAULT_MODEL, DEFAULT_USER_ID
from providers import get_provider


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_SUPPORTED_MODELS = [
    {"id": "deepseek-chat", "object": "model"},
    {"id": "qwen-plus", "object": "model"},
    {"id": "qwen-turbo", "object": "model"},
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_models() -> dict:
    """Return supported models for OpenAI-compatible clients.

    Returns:
        OpenAI-format models list response.
    """
    return {
        "object": "list",
        "data": _SUPPORTED_MODELS,
    }


async def chat_completions(req: dict = Body(...)) -> dict:
    """OpenAI-compatible chat completions endpoint.

    Supports messages (system/user/assistant) with model selection.
    stream=False only (streaming not supported).

    Args:
        req: Request body dict with model, messages, stream, session_id.

    Returns:
        OpenAI-format chat completion response.

    Raises:
        HTTPException: If messages empty, no user message, or stream=true.
    """
    model = req.get("model", DEFAULT_MODEL)
    messages = req.get("messages", [])
    stream = req.get("stream", False)

    # Validate request
    if not messages:
        raise HTTPException(
            status_code=400,
            detail="messages is required and cannot be empty",
        )

    system_prompt, context, question = parse_messages(messages)
    if not question:
        raise HTTPException(
            status_code=400,
            detail="At least one user message is required",
        )

    # Reject streaming requests
    if stream:
        raise HTTPException(
            status_code=400,
            detail="stream=true not supported",
        )

    # Setup
    cfg = get_config()
    ws = cfg.paths.user_workspace()
    db_path = cfg.paths.db_path()
    session_id = req.get("session_id") or new_session_id()

    # Get provider by model
    provider = get_provider(model=model)

    # Run ReAct
    try:
        answer, meta = await run_react(
            question=question,
            provider=provider,
            workspace_root=ws,
            session_id=session_id,
            user_id=DEFAULT_USER_ID,
            skill_filter=None,
            context=context if context else None,
            db_path=db_path,
            system_prompt_override=system_prompt or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Build OpenAI-format response
    usage = meta.get("tokens", 0)
    return {
        "id": f"chatcmpl-{__import__('uuid').uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": usage,
            "total_tokens": usage,
        },
    }
