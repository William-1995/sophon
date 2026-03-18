"""Fetch skill constants."""

# HTTP request limits
FETCH_DEFAULT_TIMEOUT_SEC = 30
FETCH_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB
FETCH_MAX_TIMEOUT_SEC = 120
FETCH_MIN_TIMEOUT_SEC = 1
FETCH_ABSOLUTE_MAX_BYTES = 50 * 1024 * 1024  # 50 MiB ceiling
FETCH_MIN_MAX_BYTES = 1024
OBSERVATION_PREVIEW_LEN = 500

# Content-Type prefixes that indicate binary (return as base64)
BINARY_CONTENT_TYPE_PREFIXES = (
    "application/pdf",
    "application/octet-stream",
    "image/",
    "audio/",
    "video/",
)
