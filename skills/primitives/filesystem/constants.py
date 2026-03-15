"""Filesystem skill constants."""

DEFAULT_QUERY_LIMIT = 200
DEFAULT_ENCODING = "utf-8"
DELETE_PARALLEL_WORKERS = 8  # max workers for parallel batch delete

# Delete confirmation (two-phase flow)
DECISION_REQUEST_KEY = "__decision_request"
CONFIRM_CHOICE = "Confirm"
CANCEL_CHOICE = "Cancel"
