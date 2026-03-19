---
name: filesystem
description: List, read, write, delete, rename files in workspace, and read system/skills docs
metadata:
  type: primitive
  dependencies: ""
---

## Orchestration Guidance

There is no `search` action. To find files by name or pattern, use `list` with `filter_pattern` and `recursive: true`.

When the user asks to save or write "my question", "what I asked", "the previous message", "what I just said", or similar without providing the content: (1) Prioritize the most recent rounds (default 3; configurable via referent_context_rounds) — e.g. "write to local" after you just gave a plan means the assistant's last response. (2) If needed, call memory.detail (omit session_id for current session) or memory.explore to retrieve it. (3) If still uncertain, ask the user to specify the content before writing.

## Workspace

**Important**: You are ALREADY inside the user's workspace. Path is relative to workspace root.
- For files at root: use `path: "filename.md"` NOT `path: "workspace/filename.md"`
- Use path "." or "" only for list/count (directory listing)
- Example: create test.md at root → `{"path": "test.md", "content": "..."}` (not workspace/test.md)

## Tools

### list
List files and directories in workspace. Also use this to search or find files by name pattern — there is no separate search action.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| path | string | No | Directory path (default: "." meaning workspace root) |
| sort_by | string | No | Sort by: "name", "size", "mtime" (default: "name") |
| order | string | No | Order: "asc" or "desc" (default: "asc") |
| filter_pattern | string | No | Glob pattern to filter by name, e.g. "*.py", "report-*.md" |
| recursive | boolean | No | Recursive listing (default: false) |

To find files by name or extension, use `filter_pattern` with `recursive: true`. Do not call list multiple times — one recursive call is sufficient.

### read
Read file content from workspace.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| path | string | Yes | File path relative to workspace |
| offset | integer | No | Start line (0-based, default: 0) |
| limit | integer | No | Max lines, 0=unlimited (default: 0) |
| tail | integer | No | Read last N lines (default: 0) |
| encoding | string | No | File encoding (default: "utf-8") |
| regex | string | No | Regex filter, only return matching lines |

### write
Write content to file in workspace.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| path | string | Yes | File path relative to workspace |
| content | string | Yes | Content to write |

### delete
Delete file(s) in workspace.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| path | string | No | Single file path to delete |
| files | array | No | Multiple file paths to delete |

**Note**: Use either `path` for single file or `files` for multiple files.

### rename
Rename a file in workspace.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| path | string | Yes | Current file path |
| new_name | string | Yes | New filename |

### count
Count files and directories.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| path | string | No | Directory path (default: root) |
| pattern | string | No | Filter pattern like "*.py" (default: "*") |
| recursive | boolean | No | Recursive count (default: true) |

### info
Get detailed file information.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| path | string | Yes | File path |

### read_skill_readme
Read a skill's README.md for installation and usage details.

Use when the user asks about setup, dependencies, installation (e.g. pip, LibreOffice), or how a skill works. Each skill's README documents capabilities, pip packages, system requirements, and platform-specific install commands.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| skill_name | string | Yes | Skill name (e.g. word, pdf, excel, emotion-awareness) |

**Example**: User asks "how do I install LibreOffice for Word?" → call with `skill_name: "word"` to get the README with install instructions.

### read_docs
Read Sophon project docs (sophon/docs/) — setup, architecture, API, create-skill.

Use when the user asks about Sophon setup, environment, architecture, API endpoints, or how to create a skill. Docs are: SETUP, ARCHITECTURE, API, create-skill.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| doc | string | No | Doc name (e.g. SETUP, ARCHITECTURE, API, create-skill). Use "list" to list available docs. |

**Example**: User asks "how do I set up Sophon?" → call with `doc: "SETUP"`. For "what's the architecture?" → `doc: "ARCHITECTURE"`.
