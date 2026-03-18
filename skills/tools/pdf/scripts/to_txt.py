#!/usr/bin/env python3
"""Convert PDF to plain text (.txt). Optional: write to output_path."""
import base64
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPTS_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Reuse parse logic
from parse import _ensure_in_workspace, _parse_pdf_bytes

try:
    from constants import PDF_MAX_PAGES
except ImportError:
    PDF_MAX_PAGES = 500


def main() -> None:
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    workspace_root = Path(params.get("workspace_root", ""))

    path = (args.get("path") or "").strip()
    content_base64 = (args.get("content_base64") or "").strip()
    output_path = (args.get("output_path") or "").strip() or None
    page_range = (args.get("page_range") or "").strip() or None
    offset = args.get("offset")
    limit = args.get("limit")
    if offset is not None:
        offset = int(offset)
    if limit is not None:
        limit = int(limit)

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

        text_by_page, _, total_pages = _parse_pdf_bytes(data, page_range, offset, limit)
        content = "\n\n".join(text_by_page) or "(no extractable text)"

        result: dict = {"content": content, "format": "txt", "extracted_pages": len(text_by_page), "total_pages": total_pages}

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
