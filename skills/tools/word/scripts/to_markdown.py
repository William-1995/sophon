#!/usr/bin/env python3
"""Convert Word (.docx) to Markdown (.md). Tables as markdown tables. Optional: write to output_path.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import base64
import json
import sys
from pathlib import Path

from parse import _ensure_in_workspace, _parse_word_bytes


def _escape_md(s: str) -> str:
    """Escape pipe for markdown table cells."""
    return str(s).replace("|", "\\|").replace("\n", " ")


def _table_to_markdown(rows: list[list[str]]) -> str:
    """Convert a table (list of rows, each row is list of cell strings) to markdown."""
    if not rows:
        return ""
    header = rows[0]
    lines = ["| " + " | ".join(_escape_md(c) for c in header) + " |"]
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in rows[1:]:
        cells = row[: len(header)]
        if len(cells) < len(header):
            cells.extend([""] * (len(header) - len(cells)))
        lines.append("| " + " | ".join(_escape_md(c) for c in cells) + " |")
    return "\n".join(lines)


def _to_markdown_content(paragraphs: list[str], tables: list[list[list[str]]]) -> str:
    """Convert paragraphs and tables to markdown. Tables interleaved by document order (simplified: pars then tables)."""
    parts: list[str] = []
    parts.extend(p for p in paragraphs if p.strip())
    for tbl in tables:
        md = _table_to_markdown(tbl)
        if md:
            parts.append(md)
    return "\n\n".join(parts) or "(no extractable content)"


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    workspace_root = Path(params.get("workspace_root", ""))

    path = (args.get("path") or "").strip()
    content_base64 = (args.get("content_base64") or "").strip()
    output_path = (args.get("output_path") or "").strip() or None

    if path and content_base64:
        print(json.dumps({"error": "Provide path OR content_base64, not both"}))
        return
    if not path and not content_base64:
        print(json.dumps({"error": "path or content_base64 is required"}))
        return

    try:
        if content_base64:
            data = base64.standard_b64decode(content_base64)
        else:
            target = (workspace_root / path).resolve()
            if not target.exists() or not target.is_file():
                print(json.dumps({"error": f"File not found: {path}"}))
                return
            if not _ensure_in_workspace(workspace_root, target):
                print(json.dumps({"error": "Path cannot escape workspace"}))
                return
            data = target.read_bytes()

        path_hint = path if path else None
        paragraphs, tables = _parse_word_bytes(data, path_hint)
        content = _to_markdown_content(paragraphs, tables)

        result: dict = {"content": content, "format": "markdown", "paragraphs": len(paragraphs), "tables": len(tables)}

        if output_path:
            out_target = (workspace_root / output_path).resolve()
            if not _ensure_in_workspace(workspace_root, out_target):
                print(json.dumps({"error": "output_path cannot escape workspace"}))
                return
            out_target.parent.mkdir(parents=True, exist_ok=True)
            out_target.write_text(content, encoding="utf-8")
            result["output_path"] = output_path
            result["written"] = True

        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main()
