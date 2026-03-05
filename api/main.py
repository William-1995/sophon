"""
FastAPI app for Sophon.

Endpoints:
- GET  /api/skills
- GET  /api/workspace/files
- POST /api/chat
- POST /api/chat/stream  (AG-UI SSE, live tokens)
- POST /api/chat/async   (fire-and-forget; events via GET /api/events)
- GET  /api/events       (SSE stream: TASK_STARTED / TASK_FINISHED / TASK_ERROR)
- GET  /api/health
- POST   /api/sessions
- GET    /api/sessions
- GET    /api/sessions/{id}/messages
- GET    /api/sessions/{id}/children  (child sessions for parent/child tree)
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
from db.schema import ensure_db_ready, configure_default_database, get_connection
from db import memory_long_term
from db import session_meta as db_session_meta

app = FastAPI(title="Sophon", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Global event bus for async task lifecycle (TASK_STARTED / TASK_FINISHED / TASK_ERROR). Each subscriber has a queue.
_event_subscribers: list[asyncio.Queue] = []


def _broadcast_event(event: dict) -> None:
    """Push event to all connected SSE clients (non-blocking)."""
    dead: list[asyncio.Queue] = []
    for q in _event_subscribers:
        try:
            q.put_nowait(event)
        except Exception:
            dead.append(q)
    for q in dead:
        try:
            _event_subscribers.remove(q)
        except ValueError:
            pass


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
    db_path = get_config().paths.db_path()
    configure_default_database(db_path)
    ensure_db_ready(db_path)


@app.get("/api/health")
def health():
    return {"status": "ok"}


async def _events_stream_gen():
    """SSE stream of async task events (TASK_STARTED, TASK_FINISHED, TASK_ERROR). Keeps connection alive with heartbeat."""
    queue: asyncio.Queue = asyncio.Queue()
    _event_subscribers.append(queue)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=25.0)
            except asyncio.TimeoutError:
                yield "data: {\"type\":\"heartbeat\"}\n\n"
                continue
            if event is None:
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    finally:
        try:
            _event_subscribers.remove(queue)
        except ValueError:
            pass


@app.get("/api/events")
async def events():
    """Server-Sent Events stream for async task lifecycle. Connect once; events include threadId, parentThreadId, agent, kind, status."""
    return StreamingResponse(
        _events_stream_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


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
def list_sessions(include: str | None = None, tree: bool = False):
    """
    List sessions (id, message_count, updated_at).
    include: optional comma-separated session ids to include even if empty.
    tree: if true, return roots with children (parent/child structure and status for async tasks).
    """
    db_path = _db_path()
    sessions = memory_long_term.list_sessions(db_path)
    if include:
        for sid in [s.strip() for s in include.split(",") if s.strip()]:
            if not any(se["id"] == sid for se in sessions):
                sessions.append({"id": sid, "message_count": 0, "updated_at": None})
    if not tree:
        return {"sessions": sessions}
    child_ids = db_session_meta.get_child_ids(db_path)
    roots = [s for s in sessions if s["id"] not in child_ids]
    out = []
    seen_ids: set[str] = set()
    for r in roots:
        children = db_session_meta.get_children(db_path, r["id"])
        seen_ids.add(r["id"])
        for c in children:
            seen_ids.add(c["session_id"])
        out.append({"id": r["id"], "message_count": r["message_count"], "updated_at": r["updated_at"], "children": children})
    # Include parents that have children but may have no messages (so list_sessions missed them)
    for parent_id in db_session_meta.get_parent_ids(db_path):
        if parent_id not in seen_ids:
            seen_ids.add(parent_id)
            children = db_session_meta.get_children(db_path, parent_id)
            for c in children:
                seen_ids.add(c["session_id"])
            out.append({"id": parent_id, "message_count": 0, "updated_at": None, "children": children})
    if include:
        for raw in [s.strip() for s in include.split(",") if s.strip()]:
            sid = _resolve_session(db_path, raw) or raw
            if sid not in seen_ids:
                out.append({"id": sid, "message_count": 0, "updated_at": None, "children": db_session_meta.get_children(db_path, sid)})
    return {"roots": out}


@app.get("/api/sessions/{session_id}/children")
def get_session_children(session_id: str):
    """List child sessions (async task tree). Returns meta with title, agent, kind, status, created_at, updated_at."""
    db_path = _db_path()
    sid = _resolve_session(db_path, session_id)
    if sid is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    children = db_session_meta.get_children(db_path, sid)
    return {"session_id": sid, "children": children}


def _resolve_session(db_path: Path, session_id: str) -> str | None:
    """Resolve partial session_id (e.g. dba17e07) to full id (e.g. web-dba17e07)."""
    resolved = memory_long_term.resolve_session_id(db_path, session_id)
    if resolved:
        return resolved
    if db_path.exists():
        conn = get_connection()
        try:
            cur = conn.execute("SELECT 1 FROM memory_long_term WHERE session_id = ? LIMIT 1", (session_id,))
            if cur.fetchone():
                return session_id
        finally:
            conn.close()
        # Parent with no messages: resolve via session_meta (children's parent_id)
        for pid in db_session_meta.get_parent_ids(db_path):
            if pid == session_id or (len(session_id) >= 6 and pid.endswith(session_id)):
                return pid
    return None


@app.get("/api/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    """Get messages for a session. Supports partial session_id. Includes status when session has session_meta (async task)."""
    db_path = _db_path()
    sid = _resolve_session(db_path, session_id)
    if sid is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    msgs = memory_long_term.get_messages(db_path, sid)
    out: dict = {"session_id": sid, "messages": msgs}
    if db_path.exists():
        meta = db_session_meta.get(db_path, sid)
        if meta:
            out["status"] = meta["status"]
    return out


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete session and its memory. Cascade deletes all children. Supports partial session_id."""
    db_path = _db_path()
    sid = _resolve_session(db_path, session_id)
    if sid is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    if db_path.exists():
        for child in db_session_meta.get_children(db_path, sid):
            memory_long_term.delete_by_session(db_path, child["session_id"])
            db_session_meta.delete_session(db_path, child["session_id"])
        memory_long_term.delete_by_session(db_path, sid)
        db_session_meta.delete_session(db_path, sid)
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
    """Background: run ReAct for child session, persist messages, update meta, broadcast TASK_FINISHED/TASK_ERROR."""
    cfg = get_config()
    db_path = _db_path()
    ws = cfg.paths.user_workspace()
    provider = get_provider(model=model)
    context = None
    if child_session_id and db_path.exists():
        context = memory_long_term.get_recent(db_path, child_session_id, limit=cfg.memory.history_recent_count)
    try:
        db_session_meta.update_status(db_path, child_session_id, "running")
        answer, meta = await run_react(
            question=message,
            provider=provider,
            workspace_root=ws,
            session_id=child_session_id,
            user_id="default_user",
            skill_filter=skill,
            context=context if context else None,
            db_path=db_path,
        )
        refs = meta.get("references") or []
        if db_path.exists():
            memory_long_term.insert(db_path, child_session_id, "assistant", answer, references=refs if refs else None)
        db_session_meta.update_status(db_path, child_session_id, "done")
        summary = (answer[:120] + "...") if len(answer) > 120 else answer
        _broadcast_event({
            "type": "TASK_FINISHED",
            "threadId": child_session_id,
            "parentThreadId": parent_session_id,
            "runId": run_id,
            "agent": agent,
            "kind": kind,
            "label": title,
            "result": {"session_id": child_session_id, "tokens": meta.get("tokens", 0), "summary": summary},
        })
    except Exception as e:
        if db_path.exists():
            db_session_meta.update_status(db_path, child_session_id, "failed")
            from db.logs import insert as log_insert
            log_insert(db_path, "ERROR", f"async_task_error: {e}", child_session_id, {"error": str(e)})
        _broadcast_event({
            "type": "TASK_ERROR",
            "threadId": child_session_id,
            "parentThreadId": parent_session_id,
            "runId": run_id,
            "agent": agent,
            "kind": kind,
            "label": title,
            "message": str(e),
        })


@app.post("/api/chat/async")
async def chat_async(req: ChatRequest):
    """Submit a message as a background task. Returns immediately with child_session_id. Events streamed via GET /api/events."""
    from db.recent_files import add as add_recent_file
    import re
    cfg = get_config()
    db_path = _db_path()

    # Only allow parent->child, not child->child (single level)
    if req.session_id and db_path.exists():
        meta = db_session_meta.get(db_path, req.session_id)
        if meta and meta.get("parent_id") is not None:
            raise HTTPException(
                status_code=400,
                detail="Cannot run background task from a child session. Switch to parent session first.",
            )

    child_session_id = _new_session_id()
    parent_session_id = req.session_id
    title = (req.message.strip()[:80] + "…") if len(req.message.strip()) > 80 else req.message.strip()
    agent = req.skill or "main"
    kind = "research" if (req.skill and "research" in req.skill.lower()) else ("crawl" if (req.skill and "crawler" in (req.skill or "").lower()) else "chat")
    run_id = str(uuid.uuid4())
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
    for m in re.finditer(r"@([^\s]+)", req.message):
        add_recent_file(db_path, m.group(1))
    if db_path.exists() and parent_session_id:
        memory_long_term.insert(db_path, parent_session_id, "user", f"[Background] {req.message.strip()}")
    _broadcast_event({
        "type": "TASK_STARTED",
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
    ))
    return {
        "child_session_id": child_session_id,
        "parent_session_id": parent_session_id,
        "status": "accepted",
        "agent": agent,
        "kind": kind,
        "run_id": run_id,
    }


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
