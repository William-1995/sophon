# Creating a Sophon Skill

Skills are the primary extension point in Sophon. A skill is a self-contained directory containing a `SKILL.md` definition and one or more Python scripts. The platform discovers and loads skills automatically — no registration or configuration code required.

This guide is written for developers working in an AI-assisted IDE (Cursor, GitHub Copilot, etc.). The skill format is designed so that an LLM can generate a correct skill from the spec alone.

---

## Skill Types

| Type | Location | Purpose |
|------|----------|---------|
| `primitive` | `skills/primitives/<name>/` | Single-purpose tool: one concern, clean input/output |
| `feature` | `skills/features/<name>/` | Orchestrates primitives to solve a higher-level user need |

Start with a primitive. Build a feature only when you need to coordinate multiple primitives or run a multi-step pipeline.

---

## Directory Structure

```
skills/primitives/my-skill/
+-- SKILL.md
+-- scripts/
|   +-- query.py        <- one file per action
|   +-- analyze.py
+-- schemas/            <- optional: JSON Schema for output validation
    +-- query_output.json
```

Rules:
- The directory name must be **kebab-case** (lowercase, hyphens only).
- It must exactly match the `name` field in `SKILL.md`.
- Each action maps to one script file: `scripts/<action>.py`.

---

## SKILL.md Specification

The `SKILL.md` file defines everything the agent needs to understand and call your skill. It follows the [Anthropic Agent Skills](https://agentskills.io/) format.

```markdown
---
name: my-skill
description: "One sentence: what this skill does and when to use it. 200 chars max."
metadata:
  type: primitive
  dependencies: ""
license: MIT
compatibility: "sophon>=1"
---

## Orchestration Guidance

When and how the main agent should invoke this skill. Be specific about
what questions or intents should trigger it.

## Tools

### action-name
What this action does.

| Parameter | Type    | Required | Description              |
|-----------|---------|----------|--------------------------|
| query     | string  | Yes      | The input to process     |
| limit     | integer | No       | Max results, default 5   |

## Output Contract

| Field       | Type   | Description                                                  |
|-------------|--------|--------------------------------------------------------------|
| result      | string | The primary output                                           |
| observation | string | Optional. LLM-ready text for the main agent. When present, the agent uses this verbatim instead of JSON. |
| references  | array  | Optional. `[{title, url}]` — sources/citations. Main agent merges and dedupes; UI renders collapsible. |
| error       | string | Present only on failure                                      |
```

### Frontmatter fields

| Field | Required | Constraint |
|-------|----------|------------|
| `name` | Yes | Kebab-case, matches directory name, 64 chars max |
| `description` | Yes | Plain text, 200 chars max; used in LLM tool descriptions |
| `metadata.type` | Recommended | `primitive` or `feature` |
| `metadata.dependencies` | Feature only | Comma-separated names of required primitives |
| `license` | Recommended | e.g. `MIT` |
| `compatibility` | Recommended | e.g. `sophon>=1` |

### Writing a good description

The description is injected directly into the LLM's tool schema. A good description:
- States the primary action in the first few words
- Names the data sources or APIs involved
- Clarifies when to use it vs. similar skills

Bad: `"Does web stuff."`
Good: `"Search the web via DuckDuckGo. Use for real-time info, news, or when user asks to search or look up."`

---

## Script Contract

Each script in `scripts/` must:
1. Read a JSON object from **stdin**
2. Write a single JSON object to **stdout**
3. Exit with code 0 on success, non-zero on unrecoverable failure

The executor injects these fields into stdin:

| Field | Type | Description |
|-------|------|-------------|
| `arguments` | object | The tool arguments from the LLM call |
| `workspace_root` | string | Absolute path to the user's workspace directory |
| `user_id` | string | Current user identifier |
| `_executor_session_id` | string | Current session ID |
| `db_path` | string | Path to `sophon.db`, if available |

Always read arguments from `params.get("arguments") or params` to handle both direct and wrapped calls.

On failure, return `{"error": "description"}` — never raise an unhandled exception. The agent will relay the error message to the user.

---

## Minimal Primitive Skill

```python
#!/usr/bin/env python3
"""my-skill/query action."""
import json
import sys


def query(text: str, limit: int = 5) -> dict:
    # Replace with real implementation
    words = text.split()[:limit]
    return {"result": " ".join(words)}


def main() -> None:
    params = json.loads(sys.stdin.read())
    args = params.get("arguments") or params
    try:
        result = query(
            text=str(args.get("text", "")).strip(),
            limit=int(args.get("limit", 5)),
        )
    except Exception as exc:
        result = {"error": str(exc)}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

---

## Feature Skill with LLM and Primitive Calls

A feature skill runs asynchronously and can call other skills via `execute_skill` and call the LLM via `get_provider`.

```python
#!/usr/bin/env python3
"""my-feature/run action."""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# SOPHON_ROOT is injected by the executor as an environment variable.
# The fallback path traversal is used only when running the script directly.
_project_root = Path(os.environ.get(
    "SOPHON_ROOT",
    Path(__file__).resolve().parent.parent.parent.parent.parent,
))
_lib_dir = Path(__file__).resolve().parent / "_lib"
for _p in (_project_root, _lib_dir):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from core.executor import execute_skill
from core.providers import get_provider

logger = logging.getLogger(__name__)


async def run(params: dict) -> dict:
    args = params.get("arguments") or params
    topic = str(args.get("topic", "")).strip()
    if not topic:
        return {"error": "topic is required"}

    workspace_root = Path(params.get("workspace_root", ""))
    session_id = params.get("_executor_session_id", "default")
    user_id = params.get("user_id", "default_user")

    search_result = await execute_skill(
        skill_name="search",
        action="search",
        arguments={"query": topic, "num": 5},
        workspace_root=workspace_root,
        session_id=session_id,
        user_id=user_id,
    )
    if search_result.get("error"):
        return {"error": f"search failed: {search_result['error']}"}

    provider = get_provider()
    resp = await provider.chat(
        [{"role": "user", "content": f"Summarize: {search_result}"}],
        system_prompt="You are a concise research assistant.",
    )

    return {
        "summary": resp.get("content", ""),
        "sources": search_result.get("results", []),
    }


def main() -> None:
    params = json.loads(sys.stdin.read())
    result = asyncio.run(run(params))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

---

## Expose the Skill

Add the skill name to `config.py` so it appears in the UI and skill selector:

```python
@dataclass(frozen=True)
class SkillConfig:
    exposed_skills: tuple[str, ...] = (
        "troubleshoot",
        "deep-research",
        "search",
        "filesystem",
        "my-skill",   # add here
    )
```

Skills not listed in `exposed_skills` are still callable by the agent internally (as dependencies) but are not shown in the UI or considered for top-level skill selection.

---

## Output Schema Validation (Optional)

Place a JSON Schema file at `schemas/<action>_output.json` to validate the script output before it reaches the agent:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["result"],
  "properties": {
    "result": { "type": "string" },
    "error":  { "type": "string" }
  },
  "additionalProperties": false
}
```

The executor logs a warning when validation fails but does not block execution.

---

## Testing a Skill Locally

Skills are plain Python scripts. Test them directly without starting the server:

```bash
# Minimal test
echo '{"arguments": {"text": "hello world", "limit": 3}}' \
  | python skills/primitives/my-skill/scripts/query.py

# With workspace context
echo '{
  "arguments": {"topic": "quantum computing"},
  "workspace_root": "/tmp/sophon-test",
  "user_id": "dev",
  "_executor_session_id": "test-session"
}' | python skills/features/my-feature/scripts/run.py
```

Expected output: a single JSON object on stdout, nothing else.

---

## Toolchain (Planned)

The following tools are under development to improve the skill authoring experience:

| Tool | Status | Description |
|------|--------|-------------|
| `sophon validate` | Planned | Validate `SKILL.md` against the spec and report errors |
| `sophon lint` | Planned | Check script contract compliance and common mistakes |
| `sophon test` | Planned | Run a skill with a fixture input and assert output shape |
| IDE integration | Planned | Schema-aware autocomplete for `SKILL.md` in Cursor and VS Code |

Until these are available, use the local test command above and check the server logs for executor errors.

---

## Style Guidelines

- **One action per script file.** Do not put multiple actions in one file.
- **Validate required parameters early.** Return an error before doing any I/O.
- **No side effects on import.** Scripts are spawned as subprocesses; top-level code runs on every call.
- **Use `logger.*`, never `print`, in non-output code.** The stdout channel is reserved for the JSON result.
- **Keep descriptions factual.** The LLM uses them verbatim for tool selection.

---

## Full Example: `word-count` Primitive

```
skills/primitives/word-count/
+-- SKILL.md
+-- scripts/
    +-- count.py
```

**SKILL.md:**

```markdown
---
name: word-count
description: "Count words, lines, or characters in text or a workspace file."
metadata:
  type: primitive
license: MIT
compatibility: "sophon>=1"
---

## Tools

### count
Count tokens in text or a file.

| Parameter | Type   | Required | Description                              |
|-----------|--------|----------|------------------------------------------|
| text      | string | No       | Raw text to count                        |
| file      | string | No       | Path relative to workspace root          |
| mode      | string | No       | words / lines / chars (default: words)   |

## Output Contract

| Field | Type    | Description             |
|-------|---------|-------------------------|
| count | integer | The computed count      |
| mode  | string  | The mode that was used  |
| error | string  | Present only on failure |
```

**scripts/count.py:**

```python
#!/usr/bin/env python3
"""word-count/count action."""
import json
import sys
from pathlib import Path

_VALID_MODES = {"words", "lines", "chars"}


def count_text(text: str, mode: str) -> int:
    if mode == "lines":
        return len(text.splitlines())
    if mode == "chars":
        return len(text)
    return len(text.split())


def main() -> None:
    params = json.loads(sys.stdin.read())
    args = params.get("arguments") or params
    mode = str(args.get("mode", "words")).lower()

    if mode not in _VALID_MODES:
        print(json.dumps({"error": f"mode must be one of: {sorted(_VALID_MODES)}"}))
        return

    text = str(args.get("text", ""))

    if not text and args.get("file"):
        workspace = Path(params.get("workspace_root", ""))
        file_path = workspace / str(args["file"])
        if not file_path.exists():
            print(json.dumps({"error": f"file not found: {args['file']}"}))
            return
        text = file_path.read_text(encoding="utf-8")

    print(json.dumps({"count": count_text(text, mode), "mode": mode}))


if __name__ == "__main__":
    main()
```
