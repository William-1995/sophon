"""Memory cache - question -> result (OpenClaw style, save tokens)."""
import hashlib
import json
import time
from pathlib import Path

from db.schema import get_connection

MAX_CACHE_ENTRIES = 1000


def _normalize_question(q: str) -> str:
    return " ".join(q.strip().lower().split())


def _question_hash(q: str) -> str:
    return hashlib.sha256(_normalize_question(q).encode("utf-8")).hexdigest()[:32]


def get(db_path: Path, question: str) -> dict | None:
    """Get cached result. Returns None if miss."""
    h = _question_hash(question)
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "SELECT result_json, created_at FROM memory_cache WHERE question_hash = ?",
            (h,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"result": json.loads(row[0]), "created_at": row[1]}
    finally:
        conn.close()


def set(db_path: Path, question: str, result: dict) -> None:
    """Cache result for question."""
    h = _question_hash(question)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO memory_cache (question_hash, question, result_json, created_at) VALUES (?, ?, ?, ?)",
            (h, _normalize_question(question), json.dumps(result), time.time()),
        )
        conn.commit()
        cur = conn.execute("SELECT COUNT(*) FROM memory_cache")
        n = cur.fetchone()[0]
        if n > MAX_CACHE_ENTRIES:
            to_remove = n - MAX_CACHE_ENTRIES
            conn.execute(
                "DELETE FROM memory_cache WHERE question_hash IN (SELECT question_hash FROM memory_cache ORDER BY created_at ASC LIMIT ?)",
                (to_remove,),
            )
            conn.commit()
    finally:
        conn.close()
