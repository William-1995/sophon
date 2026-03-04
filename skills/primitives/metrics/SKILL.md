---
name: metrics
description: Query and record numeric metrics — latency, throughput, error rates, skill_latency_ms, performance trends. Use when asked about system delays, latency, performance data, or time-series charts.
metadata:
  type: primitive
  dependencies: ""
---

## Tools

### write
Write metric points.
- name (str, required)
- value (float, required)
- timestamp (float, optional): Unix timestamp
- tags (dict, optional)

### query
Query metrics for charts. Use for numeric time-series (latency, throughput).
- name (str, required)
- since (float, optional): Unix timestamp
- until (float, optional)
- aggregation (str, optional): avg, sum, max, min
- limit (int, optional): Max data points to return. Recommended: 200 for quick, 1000–5000 for full. Omit to use default.

### list
List metric names.
