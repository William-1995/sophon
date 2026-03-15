# API Reference

Sophon exposes a FastAPI-based HTTP API.

## Base URL

```
http://localhost:8080
```

## Endpoints

### Health Check

```http
GET /api/health
```

Returns service status.

### Skills

```http
GET /api/skills
```

List all available skills with their metadata.

### Models

```http
GET /api/models
```

List available LLM providers and models.

### Sessions

```http
GET /api/sessions
```

List all chat sessions.

```http
GET /api/sessions/{id}/messages
```

Get session message history.

### Workspace

```http
GET /api/workspace/files
```

List files in the workspace.

### Chat (Streaming)

```http
POST /api/chat
Content-Type: application/json

{
  "message": "Your message here",
  "skill": "optional-skill-name",
  "model": "optional-model-name",
  "session_id": "optional-existing-session",
  "resume_run_id": "optional-run-id-to-resume-from"
}
```

Returns Server-Sent Events (SSE) stream. When backend emits `DECISION_REQUIRED`, client should show modal and submit choice via `POST /api/runs/{run_id}/decision`. On `RUN_FINISHED`, `result.resumable` indicates whether Resume is available (only when cancelled with checkpoint saved).

### HITL Decision

```http
POST /api/runs/{run_id}/decision
Content-Type: application/json

{ "choice": "Confirm" }
```

Submit user choice for Human-in-the-Loop. Unblocks the waiting run.

### Emotion (Orb Ring)

```http
GET /api/emotion/latest
```

Returns `{ emotion_label, session_id }` for the most recent emotion segment. Used for orb ring color.

## OpenAI Compatibility

Sophon provides OpenAI-compatible endpoints:

```http
POST /v1/chat/completions
```

Compatible with OpenAI SDK and tools.

## Event Types

SSE events use the AG-UI protocol:

- `RUN_STARTED` / `RUN_FINISHED` / `RUN_CANCELLED` / `RUN_ERROR` — Run lifecycle
- `TEXT_MESSAGE_*` — Text chunks
- `TOOL_START` / `TOOL_END` — Tool execution
- `DECISION_REQUIRED` — HITL: backend awaits user choice; client posts to `/api/runs/{run_id}/decision`
- `CUSTOM` (name: progress, sophon_event, gen_ui) — Progress, skill events, generated UI
- `THINKING` — LLM reasoning blocks
