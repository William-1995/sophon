---
name: trace
description: Inspect execution traces, debug runs, analyze flow.
metadata:
  type: primitive
  dependencies: ""
---

## Tools

### list
List recent trace sessions. Pass limit to control how many.
- limit (int, optional): Max sessions to return. Recommended: 50 for quick, 200 for full. Omit to use default.

### query
Query traces. Stats-level, session_id optional; omit for global view.
- session_id (str, optional): Filter by session. Omit to see all traces.
- limit (int, optional): Max traces to return. Recommended: 100 for quick scan, 500–1000 for deep. Omit to use default.
- operation (str, optional): Filter by operation type
- with_errors (bool, optional): Only show spans with errors

### analyze
Statistical analysis of traces. Stats-level, session_id optional; omit for global.
- session_id (str, optional): Filter by session. Omit for global aggregate.
- metric (str, required): duration, operations, or errors
- limit (int, optional): For global scope, max traces to analyze. Recommended: 500 for quick, 2000 for deep. Omit to use default.
