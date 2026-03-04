"""
SQLite schema and connection management.

One DB per user: workspace/{user}/sophon.db
Tables: logs, traces, metrics, memory_cache, memory_long_term, recent_files
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
-- Logs: agent/system logs for query and analysis
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    session_id TEXT,
    metadata TEXT,
    created_at REAL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_session ON logs(session_id);
CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);

-- Traces: agent execution traces
CREATE TABLE IF NOT EXISTS traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    skill TEXT,
    action TEXT,
    tokens INTEGER DEFAULT 0,
    result_preview TEXT,
    metadata TEXT,
    created_at REAL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_traces_session ON traces(session_id);
CREATE INDEX IF NOT EXISTS idx_traces_timestamp ON traces(timestamp);

-- Metrics: time-series data for charts
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    name TEXT NOT NULL,
    value REAL NOT NULL,
    tags TEXT,
    created_at REAL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(name);

-- Memory cache: short-term question -> result (OpenClaw style)
CREATE TABLE IF NOT EXISTS memory_cache (
    question_hash TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at REAL DEFAULT (unixepoch())
);

-- Memory long-term: conversation history and insights
CREATE TABLE IF NOT EXISTS memory_long_term (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_memory_session ON memory_long_term(session_id);
CREATE INDEX IF NOT EXISTS idx_memory_created ON memory_long_term(created_at);

-- Recent files: @ file picker, last 7 days
CREATE TABLE IF NOT EXISTS recent_files (
    path TEXT PRIMARY KEY,
    last_used_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_recent_last_used ON recent_files(last_used_at);
"""

_FTS_SQL = """
-- FTS5 for memory content (external content = memory_long_term)
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    content,
    content='memory_long_term',
    content_rowid='id',
    tokenize='unicode61'
);

-- Keep FTS in sync with memory_long_term
CREATE TRIGGER IF NOT EXISTS memory_fts_ai AFTER INSERT ON memory_long_term BEGIN
  INSERT INTO memory_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS memory_fts_ad AFTER DELETE ON memory_long_term BEGIN
  INSERT INTO memory_fts(memory_fts, rowid, content) VALUES ('delete', old.id, old.content);
END;
CREATE TRIGGER IF NOT EXISTS memory_fts_au AFTER UPDATE ON memory_long_term BEGIN
  INSERT INTO memory_fts(memory_fts, rowid, content) VALUES ('delete', old.id, old.content);
  INSERT INTO memory_fts(rowid, content) VALUES (new.id, new.content);
END;
"""


def _add_memory_references_column(conn: sqlite3.Connection) -> None:
    """Add refs_json column to memory_long_term if missing (migration)."""
    cur = conn.execute("PRAGMA table_info(memory_long_term)")
    cols = [row[1] for row in cur.fetchall()]
    if "refs_json" not in cols:
        conn.execute("ALTER TABLE memory_long_term ADD COLUMN refs_json TEXT")
        conn.commit()
        logger.info("memory_long_term: added refs_json column")


def _ensure_memory_fts(conn: sqlite3.Connection) -> None:
    """Create FTS5 table and triggers if missing, then rebuild index from memory_long_term."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_fts'"
    )
    if cur.fetchone():
        return
    conn.executescript(_FTS_SQL)
    conn.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")
    conn.commit()
    logger.info("Memory FTS5 index created and rebuilt")


def init_db(db_path: Path) -> None:
    """
    Initialize database with schema. Idempotent.

    Args:
        db_path: Path to SQLite database file.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
        _add_memory_references_column(conn)
        _ensure_memory_fts(conn)
        logger.info("Database initialized: %s", db_path)
    finally:
        conn.close()


def get_connection(db_path: Path) -> sqlite3.Connection:
    """
    Get connection to database. Caller must close.

    Args:
        db_path: Path to SQLite file.

    Returns:
        sqlite3.Connection
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def rebuild_memory_fts(db_path: Path) -> None:
    """
    Rebuild FTS5 index from memory_long_term. Call after bulk imports.
    """
    if not db_path.exists():
        return
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_fts'"
        )
        if cur.fetchone():
            conn.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")
            conn.commit()
            logger.info("Memory FTS5 index rebuilt")
        else:
            conn.executescript(_FTS_SQL)
            conn.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")
            conn.commit()
            logger.info("Memory FTS5 index created and rebuilt")
    finally:
        conn.close()


def ensure_db_ready(db_path: Path) -> None:
    """
    Ensure database exists and schema is applied.

    Args:
        db_path: Path to SQLite file.
    """
    init_db(db_path)
