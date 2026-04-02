"""Timestamp and duration formatting for primitive skills."""

import time
from datetime import datetime

DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_DATE_ONLY_FORMAT = "%Y-%m-%d"
SECONDS_PER_DAY = 86400


def ts_to_date(timestamp: float | int | None, fmt: str = DEFAULT_DATE_FORMAT) -> str | None:
    """Format Unix epoch seconds to a local-time string.

    Args:
        timestamp (float | int | None): Epoch seconds; ``None`` yields ``None``.
        fmt (str): ``time.strftime`` format string.

    Returns:
        str | None: Formatted time, or ``None`` if invalid.
    """
    if timestamp is None:
        return None

    try:
        ts = int(float(timestamp))
        return time.strftime(fmt, time.localtime(ts))
    except (TypeError, ValueError, OSError):
        return None


def parse_date_to_ts(date_str: str, fmt: str = DEFAULT_DATE_ONLY_FORMAT) -> float | None:
    """Parse a calendar date string to epoch seconds.

    Args:
        date_str (str): Date text.
        fmt (str): ``datetime.strptime`` format.

    Returns:
        float | None: Epoch seconds, or ``None`` on parse failure.
    """
    try:
        dt = datetime.strptime(date_str, fmt)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def format_duration(seconds: float | int) -> str:
    """Human-readable duration from seconds (e.g. ``1h 1m 1s``).

    Args:
        seconds (float | int): Non-negative duration.

    Returns:
        str: Compact duration label.
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s" if secs else f"{minutes}m"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes}m" if minutes else f"{hours}h"


def get_current_timestamp() -> int:
    """Current Unix time in seconds.

    Returns:
        int: Epoch seconds.
    """
    return int(time.time())


def add_days_to_ts(timestamp: float | int, days: int) -> float:
    """Shift a timestamp by a whole number of days.

    Args:
        timestamp (float | int): Base epoch seconds.
        days (int): Days to add (may be negative).

    Returns:
        float: Shifted timestamp.
    """
    return float(timestamp) + (days * SECONDS_PER_DAY)
