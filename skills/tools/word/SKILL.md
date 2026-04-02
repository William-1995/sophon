---
name: word
description: Read, inspect, and extract Word documents.
metadata:
  type: primitive
  dependencies: ""
---

## Workspace

- When using `path`: resolved against workspace_root. Path must be within workspace.
- When using `content_base64`: no workspace; use bytes from fetch.get (for remote .doc/.docx).

## Formats

- **.docx**: Supported via python-docx.
- **.doc**: Supported via LibreOffice (soffice) conversion. Requires `soffice` in PATH.

### Installing LibreOffice (for .doc support)

If `.doc` parsing fails with "soffice not found", install LibreOffice and ensure `soffice` is in PATH:

| Platform | Command |
|----------|---------|
| **macOS** | `brew install --cask libreoffice` |
| **Ubuntu/Debian** | `sudo apt install libreoffice-writer` |
| **Fedora/RHEL** | `sudo dnf install libreoffice-writer` |
| **Windows** | Download from [libreoffice.org](https://www.libreoffice.org/download), add install directory to PATH |

## Tools

### parse

Extract paragraphs and tables from a .doc or .docx file. Input: either local path or base64-encoded content.

| Parameter     | Type   | Required | Description |
|---------------|--------|----------|-------------|
| path          | string | No*      | Path relative to workspace (e.g. docs/report.docx or report.doc) |
| content_base64| string | No*      | Base64-encoded doc/docx bytes (from fetch.get for binary) |
| output_path   | string | No       | Write extracted content to this path (relative to workspace). |

\* Exactly one of `path` or `content_base64` is required.

Returns: `{paragraphs, tables, observation, output_path?, written?}`.
- `paragraphs`: list of paragraph text strings (document order)
- `tables`: list of tables; each table is list of rows; each row is list of cell text strings

### to_txt

Convert Word (.doc, .docx) to plain text. Optionally write to output file.

| Parameter     | Type   | Required | Description |
|---------------|--------|----------|-------------|
| path          | string | No*      | Path relative to workspace |
| content_base64| string | No*      | Base64-encoded doc/docx bytes |
| output_path   | string | No       | Write output to this path (relative to workspace) |

Returns: `{content, format: "txt", paragraphs, tables, output_path?, written?}`

### to_markdown

Convert Word (.doc, .docx) to Markdown. Tables rendered as markdown tables. Optionally write to output file.

| Parameter     | Type   | Required | Description |
|---------------|--------|----------|-------------|
| path          | string | No*      | Path relative to workspace |
| content_base64| string | No*      | Base64-encoded doc/docx bytes |
| output_path   | string | No       | Write output to this path |

Returns: `{content, format: "markdown", paragraphs, tables, output_path?, written?}`
