"""Log-analyze skill literals (self-contained; no project-level imports).

Constants:
    DB_FILENAME: Default SQLite basename.
    SECONDS_PER_DAY / ISO_DATE_* / SQL_DATE_FORMAT: Date parsing helpers.
    LOG_ANALYZE_DEFAULT_ROW_LIMIT: Default SQL row cap for analytics queries.
    LOG_ANALYZE_DEFAULT_RANGE_DAYS: Default sliding window in days.
"""

DB_FILENAME = "sophon.db"
SECONDS_PER_DAY = 86400
ISO_DATE_YYYY_MM_DD_LEN = 10
SQL_DATE_FORMAT = "%Y-%m-%d"
LOG_ANALYZE_DEFAULT_ROW_LIMIT = 10000
LOG_ANALYZE_DEFAULT_RANGE_DAYS = 7
