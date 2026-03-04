"""
FastAPI app for Sophon.

Endpoints:
- GET  /api/skills
- GET  /api/workspace/files
- POST /api/chat
- POST /api/chat/stream  (AG-UI SSE, live tokens)
- GET  /api/health
- POST   /api/sessions
- GET    /api/sessions
- GET    /api/sessions/{id}/messages
- DELETE /api/sessions/{id}
- POST   /api/sessions/{id}/fork

OpenAI-compatible:
- GET  /v1/models
- POST /v1/chat/completions  (messages with system/user/assistant, model=deepseek-chat|qwen-plus|qwen-turbo)
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import bootstrap, get_config, SESSION_ID_LENGTH
from core.skill_loader import get_skills_brief
from core.providers import get_provider
from core.react import run_react
from db.schema import ensure_db_ready
from db import memory_long_term
app = FastAPI(title="Sophon", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _db_path() -> Path:
    return get_config().paths.db_path()


def _new_session_id() -> str:
    return f"web-{uuid.uuid4().hex[:SESSION_ID_LENGTH]}"


class ChatRequest(BaseModel):
    message: str
    skill: str | None = None
    session_id: str | None = None
    model: str | None = None  # Override default (e.g. qwen-mlx, deepseek-chat)
    history: list[dict] | None = None  # deprecated: backend uses DB when session_id set


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    cache_hit: bool = False
    tokens: int = 0
    gen_ui: dict | None = None
    references: list[dict] | None = None


def _parse_messages(messages: list[dict]) -> tuple[str, list[dict], str]:
    """Extract system_prompt, context (history before last user), and last user question."""
    system_parts: list[str] = []
    user_assistant: list[dict] = []

    for m in messages or []:
        role = (m.get("role") or "user").lower()
        content = (m.get("content") or "").strip()
        if role == "system":
            if content:
                system_parts.append(content)
        elif role in ("user", "assistant"):
            user_assistant.append({"role": role, "content": content})

    system_prompt = "\n".join(system_parts).strip() if system_parts else ""
    if not user_assistant:
        return system_prompt, [], ""
    # Last user message = current question; rest = context
    last_idx = -1
    for i in range(len(user_assistant) - 1, -1, -1):
        if user_assistant[i]["role"] == "user":
            last_idx = i
            break
    if last_idx < 0:
        return system_prompt, user_assistant, ""
    question = user_assistant[last_idx]["content"]
    context = user_assistant[:last_idx]
    return system_prompt, context, question


@app.on_event("startup")
def startup():
    bootstrap()
    ensure_db_ready(get_config().paths.db_path())


@app.get("/api/health")
def health():
    return {"status": "ok"}


# -------- OpenAI-compatible endpoints --------
@app.get("/v1/models")
def list_models():
    """Return supported models for OpenAI-compatible clients."""
    return {
        "object": "list",
        "data": [
            {"id": "deepseek-chat", "object": "model"},
            {"id": "qwen-plus", "object": "model"},
            {"id": "qwen-turbo", "object": "model"},
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(req: dict = Body(...)):
    """
    OpenAI-compatible chat completions. messages (system/user/assistant), model=deepseek-chat|qwen-plus|qwen-turbo.
    stream=False only.
    """
    import time
    model = req.get("model", "deepseek-chat")
    messages = req.get("messages", [])
    stream = req.get("stream", False)

    if not messages:
        raise HTTPException(status_code=400, detail="messages is required and cannot be empty")

    system_prompt, context, question = _parse_messages(messages)
    if not question:
        raise HTTPException(status_code=400, detail="At least one user message is required")

    cfg = get_config()
    ws = cfg.paths.user_workspace()
    db_path = cfg.paths.db_path()
    session_id = req.get("session_id") or _new_session_id()

    # Select provider by model (deepseek* -> deepseek, qwen* -> qwen)
    provider = get_provider(model=model)

    try:
        answer, meta = await run_react(
            question=question,
            provider=provider,
            workspace_root=ws,
            session_id=session_id,
            user_id="default_user",
            skill_filter=None,
            context=context if context else None,
            db_path=db_path,
            system_prompt_override=system_prompt or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if stream:
        raise HTTPException(status_code=400, detail="stream=true not supported")

    # OpenAI-format response
    usage = meta.get("tokens", 0)
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
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


@app.post("/api/admin/rebuild-memory-fts")
def rebuild_memory_fts_endpoint():
    """Rebuild FTS5 index from memory_long_term. Call after bulk imports."""
    from db.schema import rebuild_memory_fts
    db_path = _db_path()
    rebuild_memory_fts(db_path)
    return {"status": "ok", "message": "Memory FTS5 index rebuilt"}


@app.get("/api/skills")
def list_skills():
    """Return skills for frontend. skill_name = mode."""
    brief = get_skills_brief()
    return {"skills": [{"name": s["skill_name"], "description": s["skill_description"]} for s in brief]}


@app.post("/api/sessions")
def create_session():
    """Create new session. Returns session_id."""
    return {"session_id": _new_session_id()}


@app.get("/api/sessions")
def list_sessions(include: str | None = None):
    """
    List sessions (id, message_count, updated_at).
    include: optional comma-separated session ids to include even if empty.
    """
    db_path = _db_path()
    sessions = memory_long_term.list_sessions(db_path)
    if include:
        for sid in [s.strip() for s in include.split(",") if s.strip()]:
            if not any(se["id"] == sid for se in sessions):
                sessions.append({"id": sid, "message_count": 0, "updated_at": None})
    return {"sessions": sessions}


def _resolve_session(db_path: Path, session_id: str) -> str | None:
    """Resolve partial session_id (e.g. dba17e07) to full id (e.g. web-dba17e07)."""
    resolved = memory_long_term.resolve_session_id(db_path, session_id)
    if resolved:
        return resolved
    if db_path.exists():
        from db.schema import get_connection
        conn = get_connection(db_path)
        try:
            cur = conn.execute("SELECT 1 FROM memory_long_term WHERE session_id = ? LIMIT 1", (session_id,))
            if cur.fetchone():
                return session_id
        finally:
            conn.close()
    return None


@app.get("/api/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    """Get messages for a session. Supports partial session_id (e.g. dba17e07 -> web-dba17e07)."""
    db_path = _db_path()
    sid = _resolve_session(db_path, session_id)
    if sid is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    msgs = memory_long_term.get_messages(db_path, sid)
    return {"session_id": sid, "messages": msgs}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete session and its memory. Supports partial session_id."""
    db_path = _db_path()
    sid = _resolve_session(db_path, session_id)
    if sid is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    if db_path.exists():
        memory_long_term.delete_by_session(db_path, sid)
    return {"deleted": sid}


@app.post("/api/sessions/{session_id}/fork")
def fork_session(session_id: str):
    """Fork session: copy history to new session. Supports partial session_id."""
    db_path = _db_path()
    sid = _resolve_session(db_path, session_id)
    if sid is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    new_id = _new_session_id()
    if db_path.exists():
        memory_long_term.copy_to_new_session(db_path, sid, new_id)
    return {"session_id": new_id}


@app.get("/api/workspace/files")
def list_workspace_files(q: str = "", recent_days: int = 7):
    """List workspace files. Recent (last 7d) first, then rest."""
    from db.recent_files import get_recent
    cfg = get_config()
    ws = cfg.paths.user_workspace()
    db_path = cfg.paths.db_path()
    recent = get_recent(db_path) if db_path.exists() else []
    if not ws.exists():
        return {"files": recent, "recent": recent}
    all_files = []
    for p in ws.rglob("*"):
        if p.is_file() and not p.name.startswith("."):
            rel = str(p.relative_to(ws))
            all_files.append(rel)
    if q:
        ql = q.lower()
        all_files = [f for f in all_files if ql in f.lower()]
    recent_valid = [f for f in recent if f in all_files]
    rest = [f for f in sorted(all_files) if f not in recent_valid]
    return {"files": recent_valid + rest[:200 - len(recent_valid)], "recent": recent_valid}


def _build_context(req: ChatRequest, session_id: str, db_path: Path) -> list[dict]:
    """Build context from DB (memory injection). Fallback to history for backward compat."""
    if session_id and db_path.exists():
        limit = get_config().memory.history_recent_count
        ctx = memory_long_term.get_recent(db_path, session_id, limit=limit)
        if ctx:
            return ctx
    if req.history:
        return [{"role": h.get("role", "user"), "content": h.get("content", "")} for h in req.history[-10:]]
    return []


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    from db.recent_files import add as add_recent_file
    import re
    cfg = get_config()
    ws = cfg.paths.user_workspace()
    db_path = cfg.paths.db_path()
    session_id = req.session_id or _new_session_id()
    model = req.model or get_config().llm.default_model
    provider = get_provider(model=model)
    for m in re.finditer(r"@([^\s]+)", req.message):
        add_recent_file(db_path, m.group(1))
    context = _build_context(req, session_id, db_path)
    try:
        answer, meta = await run_react(
            question=req.message,
            provider=provider,
            workspace_root=ws,
            session_id=session_id,
            user_id="default_user",
            skill_filter=req.skill,
            context=context if context else None,
            db_path=db_path,
        )
        refs = meta.get("references") or []
        if db_path.exists():
            memory_long_term.insert(db_path, session_id, "user", req.message)
            memory_long_term.insert(db_path, session_id, "assistant", answer, references=refs if refs else None)
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
            from db.logs import insert as log_insert
            log_insert(db_path, "ERROR", f"chat_error: {e}", session_id, {"error": str(e)})
        raise


def _ag_ui_encode(event: dict) -> str:
    """Encode AG-UI event to SSE line. Uses ag-ui-protocol when available."""
    try:
        from ag_ui.core import EventType
        from ag_ui.encoder import EventEncoder
        # Reconstruct event from dict for encoding (by_alias gives camelCase)
        encoder = EventEncoder()
        if event.get("type") == "RUN_STARTED":
            from ag_ui.core import RunStartedEvent
            ev = RunStartedEvent(type=EventType.RUN_STARTED, thread_id=event["threadId"], run_id=event["runId"])
        elif event.get("type") == "CUSTOM":
            from ag_ui.core import CustomEvent
            ev = CustomEvent(type=EventType.CUSTOM, name=event["name"], value=event["value"])
        elif event.get("type") == "TEXT_MESSAGE_START":
            from ag_ui.core import TextMessageStartEvent
            ev = TextMessageStartEvent(type=EventType.TEXT_MESSAGE_START, message_id=event["messageId"], role="assistant")
        elif event.get("type") == "TEXT_MESSAGE_CONTENT":
            from ag_ui.core import TextMessageContentEvent
            ev = TextMessageContentEvent(type=EventType.TEXT_MESSAGE_CONTENT, message_id=event["messageId"], delta=event["delta"])
        elif event.get("type") == "TEXT_MESSAGE_END":
            from ag_ui.core import TextMessageEndEvent
            ev = TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=event["messageId"])
        elif event.get("type") == "RUN_FINISHED":
            from ag_ui.core import RunFinishedEvent
            ev = RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=event["threadId"], run_id=event["runId"], result=event.get("result"))
        elif event.get("type") == "RUN_ERROR":
            from ag_ui.core import RunErrorEvent
            ev = RunErrorEvent(type=EventType.RUN_ERROR, message=event["message"])
        else:
            return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        return encoder.encode(ev)
    except ImportError:
        # Fallback: emit snake_case or camelCase JSON directly (AG-UI clients tolerate both)
        return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _stream_chat_gen(req: ChatRequest):
    """Async generator yielding AG-UI formatted SSE events for chat stream."""
    from db.recent_files import add as add_recent_file
    import re
    cfg = get_config()
    ws = cfg.paths.user_workspace()
    db_path = cfg.paths.db_path()
    session_id = req.session_id or _new_session_id()
    run_id = str(uuid.uuid4())
    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    model = req.model or get_config().llm.default_model
    provider = get_provider(model=model)
    for m in re.finditer(r"@([^\s]+)", req.message):
        add_recent_file(db_path, m.group(1))
    context = _build_context(req, session_id, db_path)

    queue: asyncio.Queue = asyncio.Queue()

    def on_progress(tokens: int, round_num: int | None):
        queue.put_nowait({"type": "CUSTOM", "name": "progress", "value": {"tokens": tokens, "round": round_num}})

    async def run():
        try:
            answer, meta = await run_react(
                question=req.message,
                provider=provider,
                workspace_root=ws,
                session_id=session_id,
                user_id="default_user",
                skill_filter=req.skill,
                context=context if context else None,
                db_path=db_path,
                progress_callback=on_progress,
            )
            refs = meta.get("references") or []
            if db_path.exists():
                memory_long_term.insert(db_path, session_id, "user", req.message)
                memory_long_term.insert(db_path, session_id, "assistant", answer, references=refs if refs else None)
            queue.put_nowait({"type": "TEXT_MESSAGE_START", "messageId": msg_id, "role": "assistant"})
            queue.put_nowait({"type": "TEXT_MESSAGE_CONTENT", "messageId": msg_id, "delta": answer})
            queue.put_nowait({"type": "TEXT_MESSAGE_END", "messageId": msg_id})
            gen_ui = meta.get("gen_ui")
            if gen_ui:
                queue.put_nowait({"type": "CUSTOM", "name": "gen_ui", "value": gen_ui})
            result_payload: dict = {
                "session_id": session_id,
                "tokens": meta.get("tokens", 0),
                "cache_hit": meta.get("cache_hit", False),
                "gen_ui": gen_ui,
            }
            if refs:
                result_payload["references"] = refs
            queue.put_nowait({
                "type": "RUN_FINISHED",
                "threadId": session_id,
                "runId": run_id,
                "result": result_payload,
            })
        except Exception as e:
            if db_path.exists():
                from db.logs import insert as log_insert
                log_insert(db_path, "ERROR", f"chat_error: {e}", session_id, {"error": str(e)})
            queue.put_nowait({"type": "RUN_ERROR", "message": str(e)})
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(run())
    # Emit RUN_STARTED immediately
    yield _ag_ui_encode({"type": "RUN_STARTED", "threadId": session_id, "runId": run_id})
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield _ag_ui_encode(item)
    finally:
        try:
            exc = task.exception() if task.done() else None
            if exc:
                yield _ag_ui_encode({"type": "RUN_ERROR", "message": str(exc)})
        except (asyncio.InvalidStateError, asyncio.CancelledError):
            pass


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Stream chat with AG-UI formatted SSE. Events: RUN_STARTED, CUSTOM(progress/gen_ui), TEXT_MESSAGE_*, RUN_FINISHED/RUN_ERROR."""
    return StreamingResponse(
        _stream_chat_gen(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
