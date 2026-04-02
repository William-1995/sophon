#!/usr/bin/env python3
"""Return PDF structure: page count, metadata, outline (TOC). No text extraction.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import base64
import json
import sys
from pathlib import Path

from common.path_utils import ensure_in_workspace as _ensure_in_workspace

try:
    from constants import PDF_MAX_PAGES
except ImportError:
    PDF_MAX_PAGES = 500


def _coerce_optional_str(val: object) -> str:
    """Tool args may be str or a single-element list from malformed JSON."""
    if val is None:
        return ""
    if isinstance(val, list):
        if len(val) == 1 and val[0] is not None:
            return str(val[0]).strip()
        return ""
    return str(val).strip()


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


def _suggest_page_ranges(total_pages: int, chunk_size: int | None = None) -> list[str] | None:
    if total_pages <= 0:
        return None
    size = chunk_size or PDF_MAX_PAGES
    if total_pages <= size:
        return None
    ranges: list[str] = []
    start = 1
    while start <= total_pages:
        end = min(start + size - 1, total_pages)
        ranges.append(f"{start}-{end}")
        start = end + 1
    return ranges


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

    result = {
        "pages": total,
        "metadata": metadata,
        "outline": outline_flat if outline_flat else None,
    }
    suggested_ranges = _suggest_page_ranges(total)
    if suggested_ranges:
        result["suggested_page_ranges"] = suggested_ranges
        result["recommended_chunk_size"] = PDF_MAX_PAGES
    return result


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    workspace_root = Path(params.get("workspace_root", ""))

    path = _coerce_optional_str(args.get("path"))
    content_base64 = _coerce_optional_str(args.get("content_base64"))

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
