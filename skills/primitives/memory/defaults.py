"""Memory primitive skill literals (self-contained; no project-level imports).

Constants:
    DB_FILENAME: Default SQLite basename.
    DEFAULT_QUERY_LIMIT: Default listing/search cap.
    SQL_DATE_FORMAT: Date string format for SQL filters.
    SECONDS_PER_DAY / END_OF_DAY_* / ISO_DATE_*: Range and display helpers.
    MEMORY_USER_CONTENT_SNIPPET_MAX_CHARS: Truncation for user content previews.
"""

DB_FILENAME = "sophon.db"
DEFAULT_QUERY_LIMIT = 200
SQL_DATE_FORMAT = "%Y-%m-%d"

# Date/time parsing and display
SECONDS_PER_DAY = 86400
END_OF_DAY_INCLUSIVE_OFFSET_SECONDS = SECONDS_PER_DAY - 1
ISO_DATE_YYYY_MM_DD_LEN = 10
MEMORY_USER_CONTENT_SNIPPET_MAX_CHARS = 200
MEMORY_SEARCH_DEFAULT_LIMIT = 200
MEMORY_SCOPE_BY_PARENT = True
