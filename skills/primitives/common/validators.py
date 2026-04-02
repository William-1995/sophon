"""Parameter validation helpers for primitive skills."""

from typing import Any


def validate_required(params: dict, *keys: str) -> list[str]:
    """Return keys that are missing or blank string in ``params``.

    Args:
        params (dict): Skill argument dict.
        *keys (str): Required field names.

    Returns:
        list[str]: Missing or empty keys; empty when all valid.
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
    """Parse ``value`` as int and clamp to ``[min_val, max_val]`` when set.

    Args:
        value (Any): Input to coerce (e.g. string from JSON).
        min_val (int | None): Inclusive lower bound.
        max_val (int | None): Inclusive upper bound.
        default (int | None): Returned on parse failure or out-of-range.

    Returns:
        int | None: Parsed int inside range, else ``default``.
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
    """Return ``value`` if it is in ``choices``; otherwise ``default``.

    Args:
        value (Any): Candidate value.
        choices (list): Allowed values.
        default (Any): Fallback when ``value`` is not in ``choices``.

    Returns:
        Any: ``value`` or ``default``.
    """
    return value if value in choices else default


def sanitize_string(value: Any, max_length: int = 1000) -> str:
    """Strip and truncate string input.

    Args:
        value (Any): Coerced with ``str``; ``None`` becomes ``""``.
        max_length (int): Maximum returned length.

    Returns:
        str: Sanitized text.
    """
    if value is None:
        return ""

    text = str(value).strip()
    return text[:max_length] if len(text) > max_length else text
