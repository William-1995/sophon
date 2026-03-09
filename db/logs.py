"""Log operations - insert and query from SQLite logs table."""
import sqlite3
import time
from pathlib import Path
from typing import Any

from db.schema import get_connection


def _conn(db_path: Path | None) -> sqlite3.Connection:
    """Connect via db_path (for subprocess skills) or get_connection() (main process)."""
    if db_path is not None and str(db_path).strip():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn
    return get_connection()


def insert(
    db_path: Path | None,
    level: str,
    message: str,
    session_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Insert log entry. Uses db_path when provided (subprocess-safe); else get_connection()."""
    conn = _conn(db_path)
    try:
        conn.execute(
            "INSERT INTO logs (timestamp, level, message, session_id, metadata) VALUES (?, ?, ?, ?, ?)",
            (
                time.time(),
                level,
                message,
                session_id,
                __import__("json").dumps(metadata) if metadata else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def query(
    db_path: Path | None,
    since: float | None = None,
    until: float | None = None,
    level: str | None = None,
    session_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query logs. Level can be comma-separated (e.g. 'ERROR,WARN')."""
    conn = _conn(db_path)
    try:
        sql = "SELECT id, timestamp, level, message, session_id, metadata FROM logs WHERE 1=1"
        params: list[Any] = []
        if since is not None:
            sql += " AND timestamp >= ?"
            params.append(since)
        if until is not None:
            sql += " AND timestamp <= ?"
            params.append(until)
        if level:
            levels = [l.strip() for l in str(level).split(",") if l.strip()]
            if levels:
                sql += " AND level IN (" + ",".join("?" * len(levels)) + ")"
                params.extend(levels)
        if session_id:
            sql += " AND session_id = ?"
            params.append(session_id)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        result = [
            {
                "id": r[0],
                "timestamp": r[1],
                "level": r[2],
                "message": r[3],
                "session_id": r[4],
                "metadata": r[5],
            }
            for r in rows
        ]
        return result
    finally:
        conn.close()
