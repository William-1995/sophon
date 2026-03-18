---
name: pdf
description: Read and parse PDF documents. Supports structure (TOC), selective page reading. Accepts local path or content_base64 (from fetch).
metadata:
  type: primitive
  dependencies: ""
---

## Workspace

- When using `path`: resolved against workspace_root. Path must be within workspace.
- When using `content_base64`: no workspace; use bytes from fetch.get (for remote PDFs).

## Tools

### structure

Return PDF structure: page count, metadata, outline (table of contents). No text extraction. Lightweight for large files. Call first to discover chapters/sections and decide which pages to parse.

| Parameter     | Type   | Required | Description |
|---------------|--------|----------|-------------|
| path          | string | No*      | Path relative to workspace |
| content_base64| string | No*      | Base64-encoded PDF bytes (from fetch.get) |

\* Exactly one of `path` or `content_base64` is required.

Returns: `{pages, metadata, outline}`. `outline` is `[{title, page, level}, ...]` (page 1-based) or null if no bookmarks.

### parse

Extract text and metadata from a PDF. Supports page_range or offset+limit for selective reading.

| Parameter     | Type   | Required | Description |
|---------------|--------|----------|-------------|
| path          | string | No*      | Path relative to workspace (e.g. docs/report.pdf) |
| content_base64| string | No*      | Base64-encoded PDF bytes (from fetch.get for binary) |
| page_range    | string | No       | Page range: "1-5", "1,3,5", or "1-" (1 to end). Omit for all. |
| offset        | int    | No       | Starting page (0-based). Use with limit for pagination. |
| limit         | int    | No       | Max pages to extract. Use with offset for pagination. |
| output_path   | string | No       | Write extracted text to this path (relative to workspace). |

\* Exactly one of `path` or `content_base64` is required.

Returns: `{pages, extracted_pages, text_by_page, metadata, observation, output_path?, written?}`.
- `pages`: total page count in document
- `extracted_pages`: number of pages actually extracted
- `text_by_page`: list of strings for requested pages
- `metadata`: author, title, creator if present
- Scanned/image-only PDFs may return empty text; OCR not supported.

## Output Contract

**Recommended flow** (like Excel: structure first, then read selectively):

1. Call `structure` to get page count and outline (chapters/sections with page numbers).
2. Use `parse` with `page_range` or `offset`+`limit` to read only the pages you need.

**Critical**: Answer only from extracted text. Never fabricate or guess content. If the text is empty or insufficient, say so instead of inventing.

### to_txt

Convert PDF to plain text. Optionally write to output file.

| Parameter     | Type   | Required | Description |
|---------------|--------|----------|-------------|
| path          | string | No*      | Path relative to workspace |
| content_base64 | string | No*      | Base64-encoded PDF bytes |
| output_path   | string | No       | Write output to this path (relative to workspace) |
| page_range    | string | No       | Page range: "1-5", "1-" etc. Omit for all. |
| offset        | int    | No       | Starting page (0-based) |
| limit         | int    | No       | Max pages to convert |

Returns: `{content, format: "txt", extracted_pages, total_pages, output_path?, written?}`

### to_markdown

Convert PDF to Markdown. Uses outline as headers when available. Optionally write to output file.

| Parameter     | Type   | Required | Description |
|---------------|--------|----------|-------------|
| path          | string | No*      | Path relative to workspace |
| content_base64| string | No*      | Base64-encoded PDF bytes |
| output_path   | string | No       | Write output to this path |
| page_range    | string | No       | Page range. Omit for all. |
| offset        | int    | No       | Starting page (0-based) |
| limit         | int    | No       | Max pages to convert |
| use_outline   | bool   | No       | Use PDF outline as headers (default: true) |

Returns: `{content, format: "markdown", extracted_pages, total_pages, output_path?, written?}`
