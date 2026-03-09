#!/usr/bin/env python3
"""Web search via DuckDuckGo. No API key."""
import json
import sys


def main() -> None:
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    query = (args.get("query") or "").strip()
    try:
        from core.ipc import get_reporter
        r = get_reporter()
        if r:
            r.emit("progress", {"phase": "search", "query": query[:50], "display_text": f"Searching: {query[:60]}"})
    except Exception:
        pass
    num = int(args.get("num", params.get("num", 5)))
    num = max(1, min(10, num))
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
