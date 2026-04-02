"""Chat endpoints: synchronous JSON, SSE stream, and fire-and-forget async tasks."""

from fastapi import APIRouter

from api.schemas.models import AsyncTaskResponse, ChatRequest, ChatResponse
from services.chat import handle_chat
from services.chat_async import handle_chat_async
from services.chat_streaming import get_streaming_response

router = APIRouter(tags=["chat"])


@router.post("/api/chat", response_model=ChatResponse)
async def post_chat(req: ChatRequest) -> ChatResponse:
    """Run one ReAct turn and return the final answer as JSON."""
    return await handle_chat(req)


@router.post("/api/chat/stream")
async def post_chat_stream(req: ChatRequest):
    """Stream AG-UI compatible SSE events for a single ReAct run."""
    return get_streaming_response(req)


@router.post("/api/chat/async")
async def post_chat_async(req: ChatRequest) -> AsyncTaskResponse:
    """Accept a message as a background task on a child session."""
    return await handle_chat_async(req)
