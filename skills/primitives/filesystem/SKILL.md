---
name: filesystem
description: List, read, write, delete, rename, count, and inspect files in the workspace.
metadata:
  type: primitive
  dependencies: ""
---

## Scope

- **Paths** are relative to the workspace root (you are already inside it). Example: `path: "docs/note.md"`, not `workspace/docs/...`.
- **`read`**: line-oriented text from files. Best for formats you treat as text (e.g. `.md`, `.txt`, `.json`, `.yaml`). Binary or non-text files may produce garbage or huge output—avoid using `read` when the file is not meaningful as decoded text lines.
- **`list` / `count` / `info`**: discover and inspect paths under the workspace. There is no separate `search` action; use `list` with `filter_pattern` and `recursive` as needed.
- **`write`**: creates or overwrites **one** file per call with the given string `content`.

**Outputs and honesty** — Only state that a file **exists** or was **saved** if this skill’s **`write`** succeeded (or you then ran **`list`** and the path appears). Chat text alone does not create files.

## Tools

### list
List files and directories in workspace.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| path | string | No | Directory path (default: "." workspace root) |
| sort_by | string | No | Sort by: "name", "size", "mtime" (default: "name") |
| order | string | No | Order: "asc" or "desc" (default: "asc") |
| filter_pattern | string | No | Glob pattern, e.g. "*.py", "report-*.md" |
| recursive | boolean | No | Recursive listing (default: false) |

### read
Read plain-text file content from workspace (line-oriented).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| path | string | Yes | File path relative to workspace |
| offset | integer | No | Start line (0-based, default: 0) |
| limit | integer | No | Max lines, 0=unlimited (default: 0) |
| tail | integer | No | Read last N lines (default: 0) |
| encoding | string | No | File encoding (default: "utf-8") |
| regex | string | No | Regex filter, only matching lines |

### write
Write `content` to `path` (relative to workspace). One call, one file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| path | string | Yes | File path relative to workspace |
| content | string | Yes | Content to write |

### delete
Delete file(s) in workspace.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| path | string | No | Single file path |
| files | array | No | Multiple file paths |

Use either `path` or `files`.

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
