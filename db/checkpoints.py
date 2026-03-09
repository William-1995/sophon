"""Run checkpoints - persist state on cancel for resume."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from db.schema import get_connection


def _conn(db_path: Path | None) -> sqlite3.Connection:
    if db_path is not None and str(db_path).strip():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn
    return get_connection()


def insert(
    db_path: Path | None,
    run_id: str,
    session_id: str,
    round_num: int,
    question: str,
    observations: list[str],
    messages: list[dict[str, Any]],
    total_tokens: int = 0,
) -> int | None:
    """Save checkpoint. Returns inserted id or None on failure."""
    try:
        conn = _conn(db_path)
        cur = conn.execute(
            """INSERT INTO run_checkpoints (run_id, session_id, round_num, question, observations_json, messages_json, total_tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                session_id,
                round_num,
                (question or "")[:2000],
                json.dumps(observations, ensure_ascii=False),
                json.dumps(messages, ensure_ascii=False),
                total_tokens,
            ),
        )
        conn.commit()
        rowid = cur.lastrowid
        conn.close()
        return rowid
    except Exception:
        return None


def get_by_run_id(db_path: Path | None, run_id: str) -> dict[str, Any] | None:
    """Load checkpoint by run_id. Returns None if not found."""
    try:
        conn = _conn(db_path)
        cur = conn.execute(
            "SELECT id, run_id, session_id, round_num, question, observations_json, messages_json, total_tokens "
            "FROM run_checkpoints WHERE run_id = ? ORDER BY created_at DESC LIMIT 1",
            (run_id,),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        obs = json.loads(row[5]) if row[5] else []
        msg = json.loads(row[6]) if row[6] else []
        return {
            "id": row[0],
            "run_id": row[1],
            "session_id": row[2],
            "round_num": row[3],
            "question": row[4],
            "observations": obs if isinstance(obs, list) else [],
            "messages": msg if isinstance(msg, list) else [],
            "total_tokens": row[7] or 0,
        }
    except Exception:
        return None


def list_by_session(db_path: Path | None, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """List checkpoints for a session, newest first."""
    try:
        conn = _conn(db_path)
        cur = conn.execute(
            "SELECT id, run_id, session_id, round_num, question, total_tokens, created_at "
            "FROM run_checkpoints WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (session_id, limit),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "run_id": r[1],
                "session_id": r[2],
                "round_num": r[3],
                "question_preview": (r[4] or "")[:200],
                "total_tokens": r[5] or 0,
                "created_at": r[6],
            }
            for r in rows
        ]
    except Exception:
        return []
