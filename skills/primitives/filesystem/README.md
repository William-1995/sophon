# Filesystem Skill

List, write, delete, rename files in the workspace. Use this skill when no more specific skill applies.
## Capabilities

- **list**: List files/dirs, glob filter, recursive

- **read**: Plain-text files only (md, txt, json, yaml, code). Not for spreadsheets or PDF/Word binaries
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
- Use the `docs` skill for Sophon docs and skill READMEs
