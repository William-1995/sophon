"""
Time utilities for primitive skills.

Provides timestamp formatting and duration calculation utilities.
"""

import time
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_DATE_ONLY_FORMAT = "%Y-%m-%d"
SECONDS_PER_DAY = 86400


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ts_to_date(timestamp: float | int | None, fmt: str = DEFAULT_DATE_FORMAT) -> str | None:
    """Format Unix timestamp to human-readable date string.

    Args:
        timestamp: Unix timestamp (seconds since epoch).
        fmt: Date format string (default: "%Y-%m-%d %H:%M:%S").

    Returns:
        Formatted date string or None if timestamp is invalid.

    Example:
        >>> ts_to_date(1704067200)
        '2024-01-01 00:00:00'
        
        >>> ts_to_date(1704067200, "%Y-%m-%d")
        '2024-01-01'
        
        >>> ts_to_date(None)
        None
    """
    if timestamp is None:
        return None
    
    try:
        ts = int(float(timestamp))
        return time.strftime(fmt, time.localtime(ts))
    except (TypeError, ValueError, OSError):
        return None


def parse_date_to_ts(date_str: str, fmt: str = DEFAULT_DATE_ONLY_FORMAT) -> float | None:
    """Parse date string to Unix timestamp.

    Args:
        date_str: Date string to parse.
        fmt: Date format string (default: "%Y-%m-%d").

    Returns:
        Unix timestamp or None if parsing fails.

    Example:
        >>> parse_date_to_ts("2024-01-01")
        1704067200.0
    """
    try:
        dt = datetime.strptime(date_str, fmt)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def format_duration(seconds: float | int) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Human-readable duration string.

    Example:
        >>> format_duration(3661)
        '1h 1m 1s'
        
        >>> format_duration(45)
        '45s'
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s" if secs else f"{minutes}m"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"


def get_current_timestamp() -> int:
    """Get current Unix timestamp.

    Returns:
        Current Unix timestamp in seconds.
    """
    return int(time.time())


def add_days_to_ts(timestamp: float | int, days: int) -> float:
    """Add days to a timestamp.

    Args:
        timestamp: Base timestamp.
        days: Number of days to add (can be negative).

    Returns:
        New timestamp with days added.
    """
    return float(timestamp) + (days * SECONDS_PER_DAY)
