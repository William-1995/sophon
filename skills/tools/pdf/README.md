# PDF Skill

Read and parse PDFs. Structure (TOC), page-range extraction, text extraction, format conversion.

## Capabilities

- **structure**: Lightweight page count, metadata, outline
- **parse**: Extract text by page with page_range/offset+limit, optionally write to file
- **to_txt**: Convert to plain text
- **to_markdown**: Convert to Markdown (outline as headers when available)

Input: local path or base64 (with fetch for remote PDFs).

## Pip Packages

| Package | Purpose |
|---------|---------|
| `pypdf` | PDF read and parse |

## Role

- Quick structure discovery before full parse
- Selective page extraction
- Convert to txt/markdown
- Use with fetch for remote PDFs

## Notes

- Scanned/image-only PDFs yield no text (no OCR).
- Recommended flow: `structure` first, then `parse` with page_range.
