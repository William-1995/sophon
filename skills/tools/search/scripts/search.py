#!/usr/bin/env python3
"""Web search via DuckDuckGo. No API key.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sys

from constants import (
    PROGRESS_SEARCH_QUERY_DISPLAY_MAX_CHARS,
    SEARCH_CAP_MAX_RESULTS,
    SEARCH_DEFAULT_MAX_RESULTS,
    SEARCH_MIN_MAX_RESULTS,
)


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    query = (args.get("query") or "").strip()
    try:
        from core.ipc import get_reporter
        r = get_reporter()
        if r:
            q_prev = query[:PROGRESS_SEARCH_QUERY_DISPLAY_MAX_CHARS]
            r.emit(
                "progress",
                {"phase": "search", "query": q_prev, "display_text": f"Searching: {q_prev}"},
            )
    except Exception:
        pass
    num = int(args.get("num", params.get("num", SEARCH_DEFAULT_MAX_RESULTS)))
    num = max(SEARCH_MIN_MAX_RESULTS, min(SEARCH_CAP_MAX_RESULTS, num))
    if not query:
        print(json.dumps({"error": "query is required"}))
        return
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        return
    if not results:
        print(json.dumps({"result": "No results found."}))
        return
    lines = []
    sources = []
    for i, item in enumerate(results, 1):
        title = item.get("title", "")
        link = item.get("href", item.get("link", ""))
        snippet = item.get("body", item.get("snippet", ""))
        lines.append(f"{i}. {title}\n   {link}\n   {snippet}")
        if link:
            sources.append({"title": title or link, "url": link})
    result_text = "\n\n".join(lines)
    references = [{"title": s["title"] or s["url"], "url": s["url"]} for s in sources]
    print(json.dumps({"result": result_text, "sources": sources, "references": references, "observation": result_text}))


if __name__ == "__main__":
    main()
