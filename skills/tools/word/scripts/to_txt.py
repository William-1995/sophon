#!/usr/bin/env python3
"""Convert Word (.docx) to plain text (.txt). Optional: write to output_path."""
import base64
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPTS_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from parse import _ensure_in_workspace, _parse_word_bytes


def _to_txt_content(paragraphs: list[str], tables: list[list[list[str]]]) -> str:
    """Convert paragraphs and tables to plain text."""
    parts: list[str] = []
    parts.extend(paragraphs)
    for tbl in tables:
        for row in tbl:
            parts.append(" | ".join(cell for cell in row))
    return "\n\n".join(parts) or "(no extractable content)"


def main() -> None:
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
        content = _to_txt_content(paragraphs, tables)

        result: dict = {"content": content, "format": "txt", "paragraphs": len(paragraphs), "tables": len(tables)}

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
