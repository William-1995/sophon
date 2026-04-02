#!/usr/bin/env python3
"""Keyword search across all conversation history (user messages only).

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from common import resolve_db_path
from defaults import MEMORY_SEARCH_DEFAULT_LIMIT
from _scope import resolve_scoped_session_ids

_CONTENT_PREVIEW = 200


def _search(
    db_path: Path,
    keyword: str,
    limit: int | None,
    scope_session_ids: list[str] | None = None,
) -> list:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    pattern = f"%{keyword}%"
    if scope_session_ids:
        placeholders = ",".join("?" * len(scope_session_ids))
        sql = (
            f"SELECT session_id, content, created_at "
            f"FROM memory_long_term WHERE role = 'user' AND content LIKE ? "
            f"AND session_id IN ({placeholders}) ORDER BY created_at DESC"
        )
        args: tuple = (pattern,) + tuple(scope_session_ids)
    else:
        sql = (
            "SELECT session_id, content, created_at "
            "FROM memory_long_term WHERE role = 'user' AND content LIKE ? ORDER BY created_at DESC"
        )
        args = (pattern,)
    if limit:
        sql += " LIMIT ?"
        args = args + (limit,)
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [
        {
            "session_id": r["session_id"],
            "time": datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d %H:%M"),
            "content": r["content"][:_CONTENT_PREVIEW],
        }
        for r in rows
        if not (r["content"] or "").startswith("[Background] ")
    ]


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = resolve_db_path(params)
    keyword = str(args.get("keyword", "")).strip()
    limit = args.get("limit")
    if limit is None:
        limit = MEMORY_SEARCH_DEFAULT_LIMIT
    else:
        limit = int(limit)

    if not db_path.exists():
        print(json.dumps({"error": "Database not found"}))
        return
    if not keyword:
        print(json.dumps({
            "error": (
                "keyword is required for search. "
                "If the user asked about a time range (e.g. 'last week'), "
                "use memory.analyze with since/until instead."
            )
        }))
        return

    scope_ids = resolve_scoped_session_ids(params, args.get("session_id") or params.get("session_id"))
    results = _search(db_path, keyword, limit, scope_session_ids=scope_ids)
    lines = [f"count={len(results)} keyword={keyword}"]
    lines.extend(f"[{r['time']}] {r['content']}" for r in results)
    print(json.dumps({
        "keyword": keyword,
        "count": len(results),
        "results": results,
        "observation": "\n".join(lines),
    }))


if __name__ == "__main__":
    main()
