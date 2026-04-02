"""SQLite path resolution and connections for primitive skills."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

DEFAULT_DB_FILENAME = "sophon.db"


def resolve_db_path(params: dict) -> Path:
    """Resolve the SQLite path from executor ``params``.

    Priority:
        1. ``params["db_path"]`` when set.
        2. ``Path(workspace_root) / sophon.db``.

    Args:
        params (dict): May contain ``db_path`` or ``workspace_root``.

    Returns:
        pathlib.Path: Database file path.
    """
    if db_path := params.get("db_path"):
        return Path(db_path)

    workspace = params.get("workspace_root", ".")
    return Path(workspace) / DEFAULT_DB_FILENAME


@contextmanager
def safe_db_connection(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Open SQLite with ``row_factory=sqlite3.Row`` and always close.

    Args:
        db_path (Path): Database file path.

    Yields:
        sqlite3.Connection: Open connection.

    Raises:
        sqlite3.Error: If the connection cannot be opened.
    """
    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        if conn:
            conn.close()


def check_db_exists(db_path: Path) -> bool:
    """Return whether the database file exists on disk.

    Args:
        db_path (Path): Candidate database path.

    Returns:
        bool: True if ``db_path`` is an existing file.
    """
    return db_path.exists()
