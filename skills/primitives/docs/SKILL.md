---
name: docs
description: Read Sophon docs and skill README files.
metadata:
  type: primitive
  dependencies: ""
---

## Scope

- Read Sophon project docs under `docs/`.
- Read a skill's `README.md` or `SKILL.md` without shell access.
- Keep the interface simple: one read action, one source of truth.

## Tools

### read
Read a Sophon doc or a skill README.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| kind | string | No | `doc` (default), `skill`, or `list` |
| name | string | No | Doc name/path or skill name |

Behavior:
- `kind: "doc"` (default): read a file from `docs/`; if `name` is omitted, list docs.
- `kind: "skill"`: read a skill README; if `name` is omitted, list available skills.
- `kind: "list"`: return both docs and skills lists.

Returns a JSON object with `content` or `docs` / `skills` plus an `observation` summary.
