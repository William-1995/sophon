"""OpenAI-shaped ``/v1/models`` and ``/v1/chat/completions`` backed by ReAct.

``stream=true`` is rejected with HTTP 400; only non-streaming completions are supported.
"""

import time
from fastapi import Body, HTTPException
from common.utils import (
    new_session_id,
    parse_messages,
)
from config import get_config
from core.react import run_react
from config.defaults import DEFAULT_MODEL
from constants import DEFAULT_USER_ID, OPENAI_COMPAT_CHATCMPL_ID_RANDOM_HEX_LEN
from providers import get_provider

_SUPPORTED_MODELS = [
    {"id": DEFAULT_MODEL, "object": "model"},
    {"id": "qwen-plus", "object": "model"},
    {"id": "qwen-turbo", "object": "model"},
]


def list_models() -> dict:
    """Static catalog of model ids exposed to OpenAI-compatible clients.

    Returns:
        Dict with ``object`` and ``data`` entries mirroring OpenAI list models.
    """
    return {
        "object": "list",
        "data": _SUPPORTED_MODELS,
    }


async def chat_completions(req: dict = Body(...)) -> dict:
    """Run ReAct once and format the answer as an OpenAI chat completion object.

    Args:
        req (dict): Body with ``model``, ``messages``, optional ``stream``,
            optional ``session_id``.

    Returns:
        JSON shaped like OpenAI ``chat.completion``.

    Raises:
        HTTPException: 400 for empty messages, missing user turn, or ``stream=true``.
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
        "id": f"chatcmpl-{__import__('uuid').uuid4().hex[:OPENAI_COMPAT_CHATCMPL_ID_RANDOM_HEX_LEN]}",
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
