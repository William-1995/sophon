"""Persist ``@file`` mentions into the recent-files table."""

from pathlib import Path

from common.utils import extract_file_references


def add_file_references_to_recent(db_path: Path, text: str) -> None:
    """Record each ``@file`` mention into the recent-files table when possible.

    Args:
        db_path (Path): SQLite path; no-op when the file does not exist.
        text (str): Arbitrary user or model text to scan for references.
    """
    if not db_path.exists():
        return

    from db.recent_files import add as add_recent_file

    for filename in extract_file_references(text):
        add_recent_file(db_path, filename)
