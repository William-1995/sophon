"""Filesystem primitive skill literals (limits, HITL keys).

Constants:
    DEFAULT_QUERY_LIMIT: Default row/file listing cap.
    DEFAULT_ENCODING: Text read/write encoding.
    DELETE_PARALLEL_WORKERS: Max workers for batch delete.
    DECISION_REQUEST_KEY / CONFIRM_CHOICE / CANCEL_CHOICE: Two-phase delete protocol.
    DECISION_PAYLOAD_AUTO_CONFIRM_IF_PLAN_CONFIRMED: Aligns with app-level HITL payload key.
"""

DEFAULT_QUERY_LIMIT = 200
DEFAULT_ENCODING = "utf-8"
DELETE_PARALLEL_WORKERS = 8  # max workers for parallel batch delete

# Delete confirmation (two-phase flow)
DECISION_REQUEST_KEY = "__decision_request"
CONFIRM_CHOICE = "Confirm"
CANCEL_CHOICE = "Cancel"
# Protocol: same key as sophon/constants.DECISION_PAYLOAD_AUTO_CONFIRM_IF_PLAN_CONFIRMED
DECISION_PAYLOAD_AUTO_CONFIRM_IF_PLAN_CONFIRMED = "auto_confirm_if_plan_confirmed"
