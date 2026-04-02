#!/usr/bin/env python3
"""Parse PDF - extract text per page and metadata. Input: path or content_base64 (from fetch).

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import base64
import json
import sys
from pathlib import Path

from common.path_utils import ensure_in_workspace as _ensure_in_workspace

try:
    from constants import OBSERVATION_PREVIEW_LEN, PDF_MAX_PAGES
except ImportError:
    PDF_MAX_PAGES = 500
    OBSERVATION_PREVIEW_LEN = 500


def _coerce_optional_str(val: object) -> str:
    """Tool args may be str or a single-element list from malformed JSON."""
    if val is None:
        return ""
    if isinstance(val, list):
        if len(val) == 1 and val[0] is not None:
            return str(val[0]).strip()
        return ""
    return str(val).strip()


def _normalize_page_range(raw: object) -> str | None:
    """LLM may pass page_range as str, int, or list (e.g. [1,2,3] or ['38-50'])."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, list):
        if not raw:
            return None
        if len(raw) == 1:
            x = raw[0]
            if isinstance(x, str):
                return x.strip() or None
            if isinstance(x, (int, float)):
                return str(int(x))
            return str(x).strip() or None
        if all(isinstance(x, (int, float)) for x in raw):
            return ",".join(str(int(x)) for x in raw)
        return ",".join(str(x).strip() for x in raw if x is not None) or None
    if isinstance(raw, (int, float)):
        return str(int(raw))
    s = str(raw).strip()
    return s or None


def _coerce_int_optional(val: object) -> int | None:
    if val is None:
        return None
    if isinstance(val, list) and len(val) == 1:
        val = val[0]
    try:
        return int(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _parse_page_range(
    page_range: str | None, offset: int | None, limit: int | None, total: int
) -> list[int]:
    """Return 0-based page indices to extract. Empty = all pages."""
    if page_range:
        # "1-5" or "1,3,5" or "1-" (1 to end)
        indices: set[int] = set()
        for part in page_range.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                start = max(1, int(a.strip() or 1))
                end_str = b.strip()
                end = int(end_str) if end_str else total
                end = min(total, max(start, end))
                for p in range(start, end + 1):
                    indices.add(p - 1)
            else:
                if part:
                    p = int(part)
                    if 1 <= p <= total:
                        indices.add(p - 1)
        order = sorted(indices)
    elif offset is not None or limit is not None:
        off = offset or 0
        lim = limit if limit is not None else total
        order = list(range(off, min(off + lim, total)))
    else:
        order = list(range(total))
    return order


def _parse_pdf_bytes(
    data: bytes,
    page_range: str | None = None,
    offset: int | None = None,
    limit: int | None = None,
) -> tuple[list[str], dict, int, bool]:
    from pypdf import PdfReader
    from io import BytesIO

    reader = PdfReader(BytesIO(data))
    total = len(reader.pages)
    indices = _parse_page_range(page_range, offset, limit, total)
    truncated = False
    if len(indices) > PDF_MAX_PAGES:
        indices = indices[:PDF_MAX_PAGES]
        truncated = True

    text_by_page: list[str] = []
    for i in indices:
        page = reader.pages[i]
        text = page.extract_text() or ""
        text_by_page.append(text)

    meta = reader.metadata
    metadata: dict[str, str] = {}
    if meta:
        for k in ("/Author", "/Title", "/Creator", "/Producer"):
            v = meta.get(k)
            if v:
                metadata[k.lstrip("/").lower()] = str(v) if not callable(v) else ""

    return text_by_page, metadata, total, truncated


def _load_input_data(
    workspace_root: Path, path: str | None, content_base64: str | None
) -> tuple[bytes | None, str | None]:
    """Load data from path or content_base64. Returns (data, error_msg)."""
    if content_base64:
        return base64.standard_b64decode(content_base64), None
    target = (workspace_root / path).resolve()
    if not target.exists() or not target.is_file():
        return None, f"File not found: {path}"
    if not _ensure_in_workspace(workspace_root, target):
        return None, "Path cannot escape workspace"
    return target.read_bytes(), None


def _maybe_write_pdf_output(
    workspace_root: Path, output_path: str | None, full_text: str
) -> bool:
    """Write full_text to output_path if set. Returns False on error."""
    if not output_path:
        return True
    out_target = (workspace_root / output_path).resolve()
    if not _ensure_in_workspace(workspace_root, out_target):
        print(json.dumps({"error": "output_path cannot escape workspace"}))
        return False
    out_target.parent.mkdir(parents=True, exist_ok=True)
    out_target.write_text(full_text, encoding="utf-8")
    return True


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
        data, err = _load_input_data(workspace_root, path or None, content_base64 or None)
        if err is not None:
            print(json.dumps({"error": err}))
            return

        text_by_page, metadata, total_pages, truncated = _parse_pdf_bytes(
            data, page_range, offset, limit
        )
        full_text = "\n\n".join(text_by_page)
        if not _maybe_write_pdf_output(workspace_root, output_path, full_text):
            return

        obs = (
            full_text[:OBSERVATION_PREVIEW_LEN] + "..."
            if len(full_text) > OBSERVATION_PREVIEW_LEN
            else full_text
        ) or "(no extractable text)"
        result = {
            "pages": total_pages,
            "extracted_pages": len(text_by_page),
            "text_by_page": text_by_page,
            "metadata": metadata,
            "observation": obs,
        }
        if truncated:
            result["truncated"] = True
            result["warning"] = (
                f"Requested more than {PDF_MAX_PAGES} selected pages; "
                "returned the first chunk only."
            )
        if output_path:
            result["output_path"] = output_path
            result["written"] = True
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main()
