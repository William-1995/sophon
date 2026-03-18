---
name: log-analyze
description: Check logs, find errors and exceptions, analyze system events.
metadata:
  type: primitive
  dependencies: ""
---

## Tools

### list
List available log sessions and dates.
- limit (int, optional): Max sessions/dates to return. Recommended: 50 for quick, 200 for full. Omit to use default.

### query
Get log entries (raw list). Use for "show/display error logs" - returns individual entries. Use level="ERROR" for errors.
No path parameter.
- since (str, optional): Start date YYYY-MM-DD
- until (str, optional): End date YYYY-MM-DD
- level (str, optional): ERROR, WARN, INFO (comma-separated)
- keyword (str, optional): Search keyword
- regex (str, optional): Regex pattern
- exclude_keyword (str, optional): Exclude logs containing this
- limit (int, optional): Max log entries to return. Recommended: 100 for quick, 500–1000 for deep. Omit to use default.
- session_id (str, optional)

### analyze
Aggregation only - for charts (count by level, time series). Use for "chart" requests only. NOT for listing raw logs - use query.
- since (str, optional): Start date YYYY-MM-DD, default 7 days ago
- until (str, optional): End date YYYY-MM-DD, default today
- limit (int, optional): Max log entries to aggregate. Recommended: 5000 for quick, 20000+ for full range. Omit to use default.
