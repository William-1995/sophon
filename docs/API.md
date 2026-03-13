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
  "session_id": "optional-existing-session"
}
```

Returns Server-Sent Events (SSE) stream with response chunks.

## OpenAI Compatibility

Sophon provides OpenAI-compatible endpoints:

```http
POST /v1/chat/completions
```

Compatible with OpenAI SDK and tools.

## Event Types

SSE events use the AG-UI protocol:

- `message` - Text response chunks
- `tool_call` - Tool execution started
- `tool_result` - Tool execution completed
- `reference` - Citation/reference added
- `done` - Response complete
- `error` - Error occurred
