"""
FastAPI app for Sophon.

Minimal main file that registers all routes and initializes the application.
All business logic is delegated to specialized modules.

Endpoints registered:
- Health: GET /api/health
- Skills: GET /api/skills
- Workspace: GET /api/workspace/files
- Sessions: POST/GET /api/sessions, GET/DELETE /api/sessions/{id}, etc.
- Chat: POST /api/chat, POST /api/chat/stream, POST /api/chat/async
- Events: GET /api/events
- Runs: POST /api/runs/{run_id}/cancel, POST /api/runs/{run_id}/decision
- Admin: POST /api/admin/rebuild-memory-fts
- OpenAI-compatible: GET /v1/models, POST /v1/chat/completions
"""

import sys
from pathlib import Path

# Ensure project root is in path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.admin import rebuild_memory_fts_endpoint
from api.async_tasks import handle_chat_async
from api.chat_handler import handle_chat
from api.events import get_events_stream
from api.models import ChatRequest, ChatResponse, DecisionRequest
from api.openai_compat import list_models, chat_completions
from api.sessions import (
    list_sessions,
    create_session,
    get_session_messages,
    get_session_children,
    delete_session,
    fork_session,
)
from api.skills import list_skills as get_skills_list
from api.state import request_cancel, submit_decision
from api.streaming import get_streaming_response
from api.workspace import list_workspace_files
from config import bootstrap
from constants import API_TITLE, API_VERSION, API_DESCRIPTION
from db.schema import ensure_db_ready, configure_default_database

# ---------------------------------------------------------------------------
# Application initialization
# ---------------------------------------------------------------------------

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    """Initialize application on startup."""
    bootstrap()
    db_path = Path(__file__).resolve().parent.parent / "workspace" / "sophon.db"
    configure_default_database(db_path)
    ensure_db_ready(db_path)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Skills endpoints
# ---------------------------------------------------------------------------

@app.get("/api/skills")
def get_skills():
    """List available skills."""
    return get_skills_list()


# ---------------------------------------------------------------------------
# Workspace endpoints
# ---------------------------------------------------------------------------

@app.get("/api/workspace/files")
def get_workspace_files(q: str = "", recent_days: int = 7):
    """List workspace files with recent files prioritized."""
    return list_workspace_files(q, recent_days)


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------

@app.post("/api/sessions")
def post_create_session():
    """Create a new session."""
    return create_session()


@app.get("/api/sessions")
def get_list_sessions(include: str | None = None, tree: bool = False):
    """List sessions with optional tree view."""
    return list_sessions(include, tree)


@app.get("/api/sessions/{session_id}/messages")
def get_messages(session_id: str):
    """Get messages for a session."""
    return get_session_messages(session_id)


@app.get("/api/sessions/{session_id}/children")
def get_children(session_id: str):
    """Get child sessions."""
    return get_session_children(session_id)


@app.delete("/api/sessions/{session_id}")
def delete_session_endpoint(session_id: str):
    """Delete a session."""
    return delete_session(session_id)


@app.post("/api/sessions/{session_id}/fork")
def fork_session_endpoint(session_id: str):
    """Fork a session."""
    return fork_session(session_id)


# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------

@app.post("/api/chat", response_model=ChatResponse)
async def post_chat(req: ChatRequest):
    """Synchronous chat endpoint."""
    return await handle_chat(req)


@app.post("/api/chat/stream")
async def post_chat_stream(req: ChatRequest):
    """Streaming chat endpoint with AG-UI formatted SSE."""
    return get_streaming_response(req)


@app.post("/api/chat/async")
async def post_chat_async(req: ChatRequest):
    """Async chat endpoint - returns immediately, runs in background."""
    return await handle_chat_async(req)


# ---------------------------------------------------------------------------
# Events endpoint
# ---------------------------------------------------------------------------

@app.get("/api/events")
async def get_events():
    """Server-Sent Events stream for async task lifecycle."""
    return get_events_stream()


# ---------------------------------------------------------------------------
# Run management endpoints
# ---------------------------------------------------------------------------

@app.post("/api/runs/{run_id}/cancel")
async def cancel_run_endpoint(run_id: str):
    """Request cancellation of a streaming run."""
    request_cancel(run_id)
    return {"status": "ok", "run_id": run_id}


@app.post("/api/runs/{run_id}/decision")
async def post_decision(run_id: str, req: DecisionRequest):
    """Submit user decision for HITL."""
    await submit_decision(run_id, req.choice)
    return {"status": "ok", "run_id": run_id}


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@app.post("/api/admin/rebuild-memory-fts")
def post_rebuild_memory_fts():
    """Rebuild FTS5 index from memory_long_term."""
    return rebuild_memory_fts_endpoint()


# ---------------------------------------------------------------------------
# OpenAI-compatible endpoints
# ---------------------------------------------------------------------------

@app.get("/v1/models")
def get_models():
    """OpenAI-compatible models list."""
    return list_models()


@app.post("/v1/chat/completions")
async def post_chat_completions(req: dict):
    """OpenAI-compatible chat completions."""
    return await chat_completions(req)
