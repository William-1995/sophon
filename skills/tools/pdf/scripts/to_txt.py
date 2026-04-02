#!/usr/bin/env python3
"""Convert PDF to plain text (.txt). Optional: write to output_path.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import base64
import json
import sys
from pathlib import Path

# Reuse parse logic
from parse import (
    _coerce_int_optional,
    _coerce_optional_str,
    _ensure_in_workspace,
    _normalize_page_range,
    _parse_pdf_bytes,
)

try:
    from constants import PDF_MAX_PAGES
except ImportError:
    PDF_MAX_PAGES = 500


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    workspace_root = Path(params.get("workspace_root", ""))

    path = _coerce_optional_str(args.get("path"))
    content_base64 = _coerce_optional_str(args.get("content_base64"))
    output_path = _coerce_optional_str(args.get("output_path")) or None
    page_range = _normalize_page_range(args.get("page_range"))
    offset = _coerce_int_optional(args.get("offset"))
    limit = _coerce_int_optional(args.get("limit"))

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

        text_by_page, _, total_pages, truncated = _parse_pdf_bytes(data, page_range, offset, limit)
        content = "\n\n".join(text_by_page) or "(no extractable text)"

        result: dict = {"content": content, "format": "txt", "extracted_pages": len(text_by_page), "total_pages": total_pages}
        if truncated:
            result["truncated"] = True
            result["warning"] = (
                f"Requested more than {PDF_MAX_PAGES} selected pages; "
                "returned the first chunk only."
            )

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
