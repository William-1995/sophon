"""Get full conversation history for a specific session."""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def main() -> None:
    params = json.loads(sys.stdin.read())
    db_path = params.get("db_path")
    session_id = str(params.get("session_id", "")).strip()

    if not db_path or not Path(db_path).exists():
        print(json.dumps({"error": "Database not found"}))
        return
    if not session_id:
        print(json.dumps({"error": "session_id is required"}))
        return

    conn = sqlite3.connect(db_path)
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
        lines.append(f"[{ts}] {m['role']}: {m['content'][:200]}")
    print(json.dumps({
        "session_id": session_id,
        "message_count": len(messages),
        "messages": messages,
        "observation": "\n".join(lines),
    }))


if __name__ == "__main__":
    main()
