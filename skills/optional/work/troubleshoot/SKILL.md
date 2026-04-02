---
name: troubleshoot
description: System anomalies, errors, latency diagnosis. Logs, traces, metrics. Orchestrates log-analyze, trace, metrics primitives. Fetches data, frontend renders charts.
metadata:
  type: feature
  dependencies: "log-analyze,trace,metrics,memory"
---

## Orchestration Guidance

When to use which primitive:

**log-analyze**
- `list`: List available log sessions and dates. Use when user asks "list logs".
- `query`: Get raw log entries (message, level). Use for error source analysis—pass level=ERROR. Use for "show/display error logs".
- `analyze`: Aggregation for charts (count by level, time series). Use when user asks for chart/graph. NOT for raw logs.

**trace**
- `list`: List recent trace sessions. Use when user asks "list traces".
- `query`: Query traces. session_id optional; omit for global view.
- `analyze`: Statistical analysis (duration, operations, errors). session_id optional for global.

**metrics**
- `list`: List metric names. Use when user asks "show metrics".
- `query`: Query single metric for charts.
- `query_multi`: Query multiple metrics for one chart (each metric a line). Use when user wants to compare/overlay metrics.
- `query_compare`: Same metric, different time periods (e.g. last 3d vs prev 3d). Call time.calculate for each period; pass {label, since, until} per period. Use since/until (not start/end).
- `write`: Write metric points. Use when recording measurements.

**troubleshoot**
- `diagnose`: Full diagnostic. Aggregates traces and logs. session_id optional; omit for global.
  - session_id (str, optional): Filter by session. Omit for global view.
  - question (str, required)
  - traces_limit (int, optional): Max traces to fetch. Recommended: 200 for quick, 1000 for deep. Omit to use default.
  - logs_limit (int, optional): Max logs to fetch. Recommended: 100 for quick, 500 for deep. Omit to use default.
  - focus (str, optional): error, performance, all

## Output Contract

Skills produce typed output. Main agent passes through without transformation. Frontend renders by protocol type, not by skill name or page-specific logic.

### diagnose

Schema: `schemas/diagnose_output.json`

| Field | Type | Description |
|-------|------|-------------|
| summary | string | Human-readable summary. Required. |
| traces_count | int | Number of traces. |
| logs_count | int | Number of log entries. |
| by_level | object | Log level counts { level: count }. |
| time_series | array | [{ date, count }] for time-based charts. |
| operation_breakdown | array | [{ operation, count }] trace operations. |
| gen_ui | object | Optional protocol for generic frontend rendering. Preferred shape: { type, payload: { charts } } or { format: 'a2ui', messages: [...] }. Frontend renders by protocol type; skills do not own page-specific UI. |
