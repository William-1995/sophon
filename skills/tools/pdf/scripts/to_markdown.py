#!/usr/bin/env python3
"""Convert PDF to Markdown (.md). Optional: use outline for headers, write to output_path."""
import base64
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPTS_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from parse import _ensure_in_workspace, _parse_page_range, _parse_pdf_bytes

try:
    from constants import PDF_MAX_PAGES
except ImportError:
    PDF_MAX_PAGES = 500


def _get_outline(data: bytes) -> list[dict] | None:
    """Extract outline from PDF. Returns [{title, page, level}, ...] or None."""
    try:
        from pypdf import PdfReader
        from io import BytesIO

        reader = PdfReader(BytesIO(data))

        def flatten(outline, rdr, result: list, level: int = 0) -> None:
            for item in outline:
                if isinstance(item, list):
                    flatten(item, rdr, result, level + 1)
                else:
                    try:
                        title = getattr(item, "title", None) or (item.get("/Title", "") if hasattr(item, "get") else "")
                        if isinstance(title, bytes):
                            title = title.decode("utf-8", errors="replace")
                        page_num = rdr.get_destination_page_number(item)
                        if page_num is not None:
                            page_num += 1
                        result.append({"title": str(title), "page": page_num, "level": level})
                    except Exception:
                        pass

        raw = reader.outline
        if not raw:
            return None
        out: list[dict] = []
        flatten(raw, reader, out)
        return out if out else None
    except Exception:
        return None


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
    use_outline = args.get("use_outline", True)
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
        indices = _parse_page_range(page_range, offset, limit, total_pages)
        outline = _get_outline(data) if use_outline else None

        parts: list[str] = []
        outline_by_page: dict[int, list[tuple[str, int]]] = {}
        extracted_pages = {indices[i] + 1 for i in range(len(text_by_page))}
        if outline:
            for o in outline:
                p = o.get("page")
                if p and p in extracted_pages:
                    outline_by_page.setdefault(p, []).append((o.get("title", ""), o.get("level", 0)))

        for i, text in enumerate(text_by_page):
            page_num = indices[i] + 1 if i < len(indices) else i + 1
            if outline_by_page.get(page_num):
                for title, level in outline_by_page[page_num]:
                    prefix = "#" * (level + 2)
                    parts.append(f"{prefix} {title}\n")
            elif not outline_by_page and total_pages > 1:
                parts.append(f"## Page {page_num}\n")
            parts.append(text.strip())
            parts.append("")

        content = "\n".join(parts).strip() or "(no extractable text)"

        result: dict = {"content": content, "format": "markdown", "extracted_pages": len(text_by_page), "total_pages": total_pages}

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
