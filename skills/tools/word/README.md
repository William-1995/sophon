# Word Skill

Parse Word (.doc, .docx) documents. Extract paragraphs and tables, convert to plain text or Markdown.

## Capabilities

- **parse**: Extract paragraphs and tables, optionally write to file
- **to_txt**: Convert to plain text
- **to_markdown**: Convert to Markdown (tables as markdown tables)

Input: local path (relative to workspace) or base64 content (with fetch for remote files).

## Pip Packages

| Package | Purpose |
|---------|---------|
| `python-docx` | Parse .docx |

## System Requirements

### .docx
Only `python-docx` is needed.

### .doc (legacy)
Requires **LibreOffice**. Uses `soffice` to convert .doc to .docx before parsing.

#### LibreOffice Install by Platform

| Platform | Command |
|----------|---------|
| **macOS** | `brew install --cask libreoffice` |
| **Ubuntu/Debian** | `sudo apt install libreoffice-writer` |
| **Fedora/RHEL** | `sudo dnf install libreoffice-writer` |
| **Windows** | Download from [libreoffice.org](https://www.libreoffice.org/download), add install dir to PATH |

Ensure `soffice` is in PATH. If .doc parsing fails with "soffice not found", install LibreOffice.

## Role

- Extract content from local or remote Word docs
- Format conversion (txt, markdown)
- Use with `fetch` for remote .doc/.docx
