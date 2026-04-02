#!/usr/bin/env python3
"""HTTP GET - fetch URL and return content. Used for PDF/Word/Excel before parse tools.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import base64
import json
import sys
from typing import Any

try:
    from constants import (
        BINARY_CONTENT_TYPE_PREFIXES,
        FETCH_ABSOLUTE_MAX_BYTES,
        FETCH_DEFAULT_TIMEOUT_SEC,
        FETCH_MAX_BYTES,
        FETCH_MAX_TIMEOUT_SEC,
        FETCH_MIN_MAX_BYTES,
        FETCH_MIN_TIMEOUT_SEC,
        OBSERVATION_PREVIEW_LEN,
        PROGRESS_URL_DISPLAY_MAX_CHARS,
    )
except ImportError:
    FETCH_DEFAULT_TIMEOUT_SEC = 30
    FETCH_MAX_BYTES = 10 * 1024 * 1024
    FETCH_MAX_TIMEOUT_SEC = 120
    FETCH_MIN_TIMEOUT_SEC = 1
    FETCH_ABSOLUTE_MAX_BYTES = 50 * 1024 * 1024
    FETCH_MIN_MAX_BYTES = 1024
    BINARY_CONTENT_TYPE_PREFIXES = (
        "application/pdf",
        "application/octet-stream",
        "image/",
        "audio/",
        "video/",
    )
    OBSERVATION_PREVIEW_LEN = 500
    PROGRESS_URL_DISPLAY_MAX_CHARS = 80


def _is_binary_content(content_type: str) -> bool:
    """Return True if content_type indicates binary payload."""
    ct = (content_type or "").strip().lower().split(";")[0]
    return any(ct.startswith(p) for p in BINARY_CONTENT_TYPE_PREFIXES)


def _fetch_url(url: str, timeout_sec: int, max_bytes: int) -> dict[str, Any]:
    """Perform HTTP GET and return content plus metadata."""
    import httpx

    with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()

        raw = resp.content
        if len(raw) > max_bytes:
            return {
                "error": f"Response too large: {len(raw)} bytes (max {max_bytes})",
                "url": url,
            }

        content_type = resp.headers.get("content-type", "").strip().split(";")[0]
        result: dict[str, Any] = {
            "content_type": content_type,
            "status_code": resp.status_code,
            "content_length": len(raw),
            "url": url,
        }

        if _is_binary_content(content_type):
            result["content_base64"] = base64.standard_b64encode(raw).decode("ascii")
        else:
            try:
                result["content"] = raw.decode("utf-8")
            except UnicodeDecodeError:
                result["content_base64"] = base64.standard_b64encode(raw).decode("ascii")

        return result


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    url = (args.get("url") or "").strip()
    if not url:
        print(json.dumps({"error": "url is required"}))
        return

    timeout_sec = int(args.get("timeout", FETCH_DEFAULT_TIMEOUT_SEC))
    timeout_sec = max(FETCH_MIN_TIMEOUT_SEC, min(FETCH_MAX_TIMEOUT_SEC, timeout_sec))
    max_bytes = int(args.get("max_bytes", FETCH_MAX_BYTES))
    max_bytes = max(FETCH_MIN_MAX_BYTES, min(FETCH_ABSOLUTE_MAX_BYTES, max_bytes))

    try:
        from core.ipc import get_reporter

        r = get_reporter()
        if r:
            r.emit(
                "progress",
                {
                    "phase": "fetch",
                    "url": url[:PROGRESS_URL_DISPLAY_MAX_CHARS],
                    "display_text": f"Fetching: {url[:PROGRESS_URL_DISPLAY_MAX_CHARS]}",
                },
            )
    except Exception:
        pass

    try:
        result = _fetch_url(url, timeout_sec, max_bytes)
        if "content" in result:
            text = result["content"]
            obs = (
                text[:OBSERVATION_PREVIEW_LEN] + "..."
                if len(text) > OBSERVATION_PREVIEW_LEN
                else text
            )
        else:
            obs = f"Fetched {result.get('content_length', 0)} bytes ({result.get('content_type', '')})"
        result["observation"] = obs
        result["references"] = [{"title": "Source", "url": url}]
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e), "url": url}))


if __name__ == "__main__":
    main()
