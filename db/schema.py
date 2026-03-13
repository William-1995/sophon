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

# Default database configuration for this process.
# For now only a single "default" database is supported and only the SQLite
# backend is implemented. The API is designed so that a PostgreSQL backend can
# be added later without changing call sites.
_DB_ENGINE: str = "sqlite"
_DB_PATH: Optional[Path] = None

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

-- Emotion segments: user+system weighted summary per time window (optional feature)
CREATE TABLE IF NOT EXISTS emotion_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    parent_session_id TEXT,
    start_at REAL NOT NULL,
    end_at REAL NOT NULL,
    user_weight REAL NOT NULL DEFAULT 0.8,
    system_weight REAL NOT NULL DEFAULT 0.2,
    user_summary TEXT,
    system_summary TEXT,
    emotion_label TEXT,
    combined_summary TEXT,
    created_at REAL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_emotion_session ON emotion_segments(session_id);
CREATE INDEX IF NOT EXISTS idx_emotion_end_at ON emotion_segments(end_at);
CREATE INDEX IF NOT EXISTS idx_emotion_parent ON emotion_segments(parent_session_id);

-- Session meta: parent/child and status for async tasks (parent_id NULL = root)
CREATE TABLE IF NOT EXISTS session_meta (
    session_id TEXT PRIMARY KEY,
    parent_id TEXT,
    title TEXT NOT NULL DEFAULT '',
    agent TEXT NOT NULL DEFAULT 'main',
    kind TEXT NOT NULL DEFAULT 'chat',
    status TEXT NOT NULL DEFAULT 'queued',
    created_at REAL NOT NULL DEFAULT (unixepoch()),
    updated_at REAL NOT NULL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_session_meta_parent ON session_meta(parent_id);
CREATE INDEX IF NOT EXISTS idx_session_meta_status ON session_meta(status);

-- Run checkpoints: saved state when user cancels; enables resume
CREATE TABLE IF NOT EXISTS run_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    round_num INTEGER NOT NULL,
    question TEXT,
    observations_json TEXT,
    messages_json TEXT,
    total_tokens INTEGER DEFAULT 0,
    created_at REAL DEFAULT (unixepoch())
);
CREATE INDEX IF NOT EXISTS idx_checkpoints_run ON run_checkpoints(run_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_session ON run_checkpoints(session_id);
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


def configure_default_database(db_path: Path, engine: str = "sqlite") -> None:
    """
    Configure the default database backend for this process.

    Args:
        db_path: Path to the database file when using the SQLite engine.
        engine: Logical engine name. Only "sqlite" is supported today.

    Raises:
        ValueError: If an unsupported engine is provided.
    """
    global _DB_ENGINE, _DB_PATH
    if engine != "sqlite":
        # TODO: Support a PostgreSQL backend.
        raise ValueError(f"Unsupported database engine: {engine}")
    _DB_ENGINE = engine
    _DB_PATH = db_path


def get_connection() -> sqlite3.Connection:
    """
    Get a connection to the configured default database. Caller must close.
    Falls back to SOPHON_DB_PATH env var when run in skill subprocess.
    """
    import os
    if _DB_ENGINE == "sqlite":
        path = _DB_PATH
        if path is None:
            env_path = os.environ.get("SOPHON_DB_PATH")
            if env_path and str(env_path).strip():
                path = Path(env_path)
        if path is None:
            raise RuntimeError("Default database is not configured. Call configure_default_database() first.")
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn
    if _DB_ENGINE == "postgres":
        # TODO: Implement PostgreSQL backend and return a pooled connection.
        raise NotImplementedError("PostgreSQL backend is not implemented yet.")
    raise RuntimeError(f"Unsupported database engine: {_DB_ENGINE}")


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
