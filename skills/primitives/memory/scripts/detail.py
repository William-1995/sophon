#!/usr/bin/env python3
"""Get full conversation history for a specific session.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sqlite3
import sys
from datetime import datetime

from common import resolve_db_path
from _scope import resolve_scoped_session_ids
from defaults import MEMORY_USER_CONTENT_SNIPPET_MAX_CHARS


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = resolve_db_path(params)
    session_id = str(args.get("session_id", "")).strip()

    if not db_path.exists():
        print(json.dumps({"error": "Database not found"}))
        return
    if not session_id:
        print(json.dumps({"error": "session_id is required"}))
        return

    scope_ids = resolve_scoped_session_ids(params, session_id)
    if isinstance(scope_ids, list) and scope_ids and session_id not in scope_ids:
        print(json.dumps({"error": f"session {session_id} is not in the current session tree"}))
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT role, content, created_at FROM memory_long_term "
        "WHERE session_id = ? ORDER BY created_at",
        (session_id,),
    ).fetchall()
    conn.close()

    messages = [
        {"role": r["role"], "content": r["content"], "timestamp": r["created_at"]}
        for r in rows
    ]
    lines = [f"session_id={session_id} message_count={len(messages)}"]
    for m in messages:
        ts = datetime.fromtimestamp(m["timestamp"]).strftime("%Y-%m-%d %H:%M") if m.get("timestamp") else ""
        lines.append(
            f"[{ts}] {m['role']}: {m['content'][:MEMORY_USER_CONTENT_SNIPPET_MAX_CHARS]}"
        )
    print(json.dumps({
        "session_id": session_id,
        "message_count": len(messages),
        "messages": messages,
        "observation": "\n".join(lines),
    }))


if __name__ == "__main__":
    main()
