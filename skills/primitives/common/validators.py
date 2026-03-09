"""
Validation utilities for primitive skills.

Provides parameter validation helpers to ensure inputs meet requirements
before processing.
"""

from typing import Any


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_required(params: dict, *keys: str) -> list[str]:
    """Validate that required keys are present and non-empty in params.

    Args:
        params: Parameters dict to validate.
        *keys: Required key names.

    Returns:
        List of missing or empty key names. Empty list if all present.

    Example:
        >>> params = {"name": "test", "value": "", "count": 5}
        >>> validate_required(params, "name", "value", "missing")
        ['value', 'missing']
    """
    missing = []
    for key in keys:
        value = params.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(key)
    return missing


def validate_int_range(
    value: Any,
    min_val: int | None = None,
    max_val: int | None = None,
    default: int | None = None,
) -> int | None:
    """Validate and convert value to integer within range.

    Args:
        value: Value to validate and convert.
        min_val: Minimum allowed value (inclusive).
        max_val: Maximum allowed value (inclusive).
        default: Default value if conversion fails.

    Returns:
        Validated integer or default if invalid.

    Example:
        >>> validate_int_range("50", 0, 100, 10)
        50
        
        >>> validate_int_range("invalid", 0, 100, 10)
        10
        
        >>> validate_int_range("200", 0, 100, 10)  # Exceeds max
        10
    """
    try:
        num = int(value)
        if min_val is not None and num < min_val:
            return default
        if max_val is not None and num > max_val:
            return default
        return num
    except (TypeError, ValueError):
        return default


def validate_choice(value: Any, choices: list, default: Any = None) -> Any:
    """Validate that value is one of allowed choices.

    Args:
        value: Value to validate.
        choices: List of allowed values.
        default: Default value if not in choices.

    Returns:
        Value if in choices, otherwise default.

    Example:
        >>> validate_choice("asc", ["asc", "desc"], "asc")
        'asc'
        
        >>> validate_choice("invalid", ["asc", "desc"], "asc")
        'asc'
    """
    return value if value in choices else default


def sanitize_string(value: Any, max_length: int = 1000) -> str:
    """Sanitize string input.

    Args:
        value: Value to sanitize.
        max_length: Maximum allowed length.

    Returns:
        Sanitized string (truncated if too long).
    """
    if value is None:
        return ""
    
    text = str(value).strip()
    return text[:max_length] if len(text) > max_length else text
