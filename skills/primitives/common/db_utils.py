"""
Database utilities for primitive skills.

Provides database connection management and path resolution for SQLite databases
used by primitive skills.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

DEFAULT_DB_FILENAME = "sophon.db"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_db_path(params: dict) -> Path:
    """Resolve database path from parameters.

    Priority:
    1. params["db_path"] if provided
    2. params["workspace_root"] / DB_FILENAME
    3. Current working directory / DB_FILENAME

    Args:
        params: Parameters dict that may contain db_path or workspace_root.

    Returns:
        Resolved Path to the database file.

    Example:
        >>> params = {"workspace_root": "/path/to/workspace"}
        >>> resolve_db_path(params)
        PosixPath('/path/to/workspace/sophon.db')
    """
    if db_path := params.get("db_path"):
        return Path(db_path)
    
    workspace = params.get("workspace_root", ".")
    return Path(workspace) / DEFAULT_DB_FILENAME


@contextmanager
def safe_db_connection(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for safe SQLite database connection.

    Ensures connection is properly closed even if an exception occurs.

    Args:
        db_path: Path to the SQLite database file.

    Yields:
        sqlite3.Connection: Database connection object.

    Example:
        >>> db_path = Path("workspace/user/sophon.db")
        >>> with safe_db_connection(db_path) as conn:
        ...     cursor = conn.execute("SELECT * FROM table")
        ...     results = cursor.fetchall()

    Raises:
        sqlite3.Error: If database connection fails.
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
    """Check if database file exists.

    Args:
        db_path: Path to check.

    Returns:
        True if database file exists, False otherwise.
    """
    return db_path.exists()
