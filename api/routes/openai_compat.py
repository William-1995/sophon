"""OpenAI-compatible ``/v1/models`` and ``/v1/chat/completions`` for third-party clients."""

from fastapi import APIRouter

from services.openai_compat import chat_completions, list_models

router = APIRouter(tags=["openai-compatible"])


@router.get("/v1/models")
def get_models() -> dict:
    """Return a static list of model ids in OpenAI list format.

    Returns:
        Dict with ``object`` and ``data`` model entries.
    """
    return list_models()


@router.post("/v1/chat/completions")
async def post_chat_completions(req: dict) -> dict:
    """Non-streaming chat completion backed by the same ReAct stack.

    Args:
        req (dict): OpenAI-style body (``model``, ``messages``, ``stream``, optional ``session_id``).

    Returns:
        OpenAI-style completion JSON.

    Raises:
        HTTPException: On validation errors or unsupported ``stream=true``.
    """
    return await chat_completions(req)
