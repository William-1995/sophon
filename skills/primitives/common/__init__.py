"""
Primitives Common - Shared utilities for primitive skills.

Provides common functionality used across all primitive skills including
database operations, path resolution, time formatting, and parameter validation.

Example:
    from common import resolve_db_path, ts_to_date, safe_db_connection
    
    db_path = resolve_db_path(params)
    with safe_db_connection(db_path) as conn:
        cursor = conn.execute("SELECT * FROM table")
"""

# Use relative imports so this works when imported from skills/primitives/
from .db_utils import resolve_db_path, safe_db_connection, check_db_exists
from .path_utils import resolve_path, resolve_directory_path
from .time_utils import ts_to_date, format_duration
from .validators import validate_required, validate_int_range, validate_choice, sanitize_string

__all__ = [
    # Database utilities
    "resolve_db_path",
    "safe_db_connection",
    "check_db_exists",
    # Path utilities  
    "resolve_path",
    "resolve_directory_path",
    # Time utilities
    "ts_to_date",
    "format_duration",
    # Validation utilities
    "validate_required",
    "validate_int_range",
    "validate_choice",
    "sanitize_string",
]
