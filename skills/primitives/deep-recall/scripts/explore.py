"""
RLM-style memory exploration.
Returns session metadata and tool map so the LLM can orient and decide next steps.
"""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def _load_session_index(db_path: str) -> dict:
    """Load lightweight session index: {session_id: {count, first_ts, last_ts}}."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT session_id, COUNT(*) as cnt, MIN(created_at) as first_ts, MAX(created_at) as last_ts "
        "FROM memory_long_term GROUP BY session_id ORDER BY last_ts DESC"
    ).fetchall()
    conn.close()
    return {
        r[0]: {"message_count": r[1], "first_ts": r[2], "last_ts": r[3]}
        for r in rows
    }


def main() -> None:
    params = json.loads(sys.stdin.read())
    db_path = params.get("db_path")
    query = str(params.get("query", "")).strip()
    session_hint = params.get("session_hint")
    max_depth = int(params.get("max_depth", 3))

    if not db_path or not Path(db_path).exists():
        print(json.dumps({"error": "Database not found", "db_path": db_path}))
        return

    index = _load_session_index(db_path)
    total_messages = sum(v["message_count"] for v in index.values())
    next_steps = (
        "Use deep-recall.search(keyword) for topic search, "
        "deep-recall.analyze(since, until) for time range, "
        "deep-recall.detail(session_id) for full session content."
    )
    lines = [f"sessions={len(index)} total_messages={total_messages}", next_steps]
    for sid, meta in list(index.items())[:20]:
        first = datetime.fromtimestamp(meta["first_ts"]).strftime("%m-%d %H:%M") if meta.get("first_ts") else ""
        last = datetime.fromtimestamp(meta["last_ts"]).strftime("%m-%d %H:%M") if meta.get("last_ts") else ""
        lines.append(f"  {sid} | {meta['message_count']} msgs | {first} -> {last}")
    if len(index) > 20:
        lines.append(f"  ... and {len(index) - 20} more sessions")

    print(json.dumps({
        "status": "ready",
        "sessions_loaded": len(index),
        "total_messages": total_messages,
        "session_index": index,
        "session_hint": session_hint,
        "query": query,
        "max_depth": max_depth,
        "next_steps": next_steps,
        "observation": "\n".join(lines),
    }))


if __name__ == "__main__":
    main()
