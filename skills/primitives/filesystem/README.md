# Filesystem Skill

List, read, write, delete, rename files in workspace.

## Capabilities

- **list**: List files/dirs, glob filter, recursive
- **read**: Read file (offset, limit, tail, regex)
- **read_skill_readme**: Read a skill's README.md (install guides, dependencies)
- **read_docs**: Read Sophon project docs (SETUP, ARCHITECTURE, API, create-skill)
- **delete**: Delete files (HITL confirm)
- **rename**: Rename file
- **count**: Count files/dirs
- **info**: File metadata

## Pip Packages

None (stdlib).

## Role

- Workspace file management
- Save agent output (reports, scripts)
- Output target for pdf/word output_path

## Notes

- Paths relative to workspace root
- Access outside workspace is blocked
