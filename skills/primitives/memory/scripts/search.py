#!/usr/bin/env python3
"""Keyword search across all conversation history (user messages only)."""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

_script_dir = Path(__file__).resolve().parent
_skill_dir = _script_dir.parent
_primitives = _skill_dir.parent
_root = _primitives.parent.parent
for p in (_skill_dir, _primitives, _root):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from common import resolve_db_path

_CONTENT_PREVIEW = 200


def _search(db_path: Path, keyword: str, limit: int | None) -> list:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    pattern = f"%{keyword}%"
    sql = (
        "SELECT session_id, content, created_at "
        "FROM memory_long_term WHERE role = 'user' AND content LIKE ? ORDER BY created_at DESC"
    )
    args: tuple = (pattern,)
    if limit:
        sql += " LIMIT ?"
        args = (pattern, limit)
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
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = resolve_db_path(params)
    keyword = str(args.get("keyword", "")).strip()
    limit = args.get("limit")
    if limit is not None:
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

    results = _search(db_path, keyword, limit)
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
