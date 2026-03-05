"""Trace operations - insert execution traces."""
import time
from pathlib import Path

from db.schema import get_connection


def insert(
    db_path: Path,
    session_id: str,
    skill: str,
    action: str,
    tokens: int = 0,
    result_preview: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Insert trace entry."""
    import json
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO traces (session_id, timestamp, skill, action, tokens, result_preview, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                time.time(),
                skill,
                action,
                tokens,
                (result_preview[:500] if result_preview else None),
                json.dumps(metadata) if metadata else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()
