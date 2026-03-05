"""Recent files - track @ file usage for last 7 days."""
import time
from pathlib import Path

from db.schema import get_connection

RECENT_DAYS_SEC = 7 * 24 * 3600


def add(db_path: Path, path: str) -> None:
    """Record file usage."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO recent_files (path, last_used_at) VALUES (?, ?)",
            (path, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent(db_path: Path, limit: int = 50) -> list[str]:
    """Get recently used files (last 7 days)."""
    cutoff = time.time() - RECENT_DAYS_SEC
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT path FROM recent_files WHERE last_used_at >= ? ORDER BY last_used_at DESC LIMIT ?",
            (cutoff, limit),
        )
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
