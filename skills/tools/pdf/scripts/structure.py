#!/usr/bin/env python3
"""Return PDF structure: page count, metadata, outline (TOC). No text extraction."""
import base64
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPTS_DIR.parent
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))



def _ensure_in_workspace(workspace_root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(workspace_root.resolve())
        return True
    except ValueError:
        return False


def _flatten_outline(outline, reader, result: list, level: int = 0) -> None:
    """Recursively flatten outline to [{title, page, level}, ...]."""
    for item in outline:
        if isinstance(item, list):
            _flatten_outline(item, reader, result, level + 1)
        else:
            try:
                title = getattr(item, "title", None)
                if title is None and hasattr(item, "get"):
                    title = item.get("/Title", "")
                if title is None:
                    title = ""
                if isinstance(title, bytes):
                    title = title.decode("utf-8", errors="replace")
                page_num = reader.get_destination_page_number(item)
                if page_num is not None:
                    page_num += 1  # 1-based for display
                result.append({"title": str(title), "page": page_num, "level": level})
            except Exception:
                pass


def _get_structure(data: bytes) -> dict:
    from pypdf import PdfReader
    from io import BytesIO

    reader = PdfReader(BytesIO(data))
    total = len(reader.pages)
    # No page limit for structure: we only read outline/metadata, not page text

    meta = reader.metadata
    metadata: dict[str, str] = {}
    if meta:
        for k in ("/Author", "/Title", "/Creator", "/Producer"):
            v = meta.get(k)
            if v:
                metadata[k.lstrip("/").lower()] = str(v) if not callable(v) else ""

    outline_flat: list[dict] = []
    try:
        raw_outline = reader.outline
        if raw_outline:
            _flatten_outline(raw_outline, reader, outline_flat)
    except Exception:
        pass

    return {
        "pages": total,
        "metadata": metadata,
        "outline": outline_flat if outline_flat else None,
    }


def main() -> None:
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    workspace_root = Path(params.get("workspace_root", ""))

    path = (args.get("path") or "").strip()
    content_base64 = (args.get("content_base64") or "").strip()

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

        result = _get_structure(data)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main()
