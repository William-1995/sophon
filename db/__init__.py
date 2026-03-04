"""Database module - SQLite for logs, traces, metrics, memory."""

from .schema import init_db, get_connection

__all__ = ["init_db", "get_connection"]
