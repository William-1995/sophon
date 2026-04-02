---
name: transform-agent
description: Transforms data between formats (CSV, PDF, Markdown, Word).
metadata:
  type: agent
  dependencies: "pdf,word,excel,filesystem"
---

## Capabilities

- CSV to JSON and vice versa
- PDF text extraction and creation
- Markdown conversion
- Word document processing
- Text file operations
- Batch conversion for multiple input files

## Supported Formats

- CSV
- JSON
- PDF
- Markdown (MD)
- TXT
- DOCX

## Input Schema

```json
{
  "input_file": "string - Path to a single input file",
  "input_files": ["string - Multiple input files"],
  "files": ["string or object - Alias for multiple input files"],
  "output_format": "string - Target format (csv/json/pdf/markdown/txt/docx)",
  "output_path": "string - Optional output file path or output directory for batch runs"
}
```

## Output Schema

```json
{
  "output_file": "string - Path to generated file (single file runs)",
  "output_files": ["string - Paths to generated files for batch runs"],
  "results": ["object - Per-file execution result"],
  "format": "string - Output format",
  "preview": "string - Content preview"
}
```
