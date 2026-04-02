#!/usr/bin/env python3
"""Trace analyze - statistical analysis of traces (SQLite-based).

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from common.db_utils import resolve_db_path

from constants import (
    TRACE_ANALYZE_DEFAULT_ROW_LIMIT,
    TRACE_ANALYZE_ERROR_SAMPLE_MAX,
    TRACE_ANALYZE_SLOWEST_OPS_COUNT,
)


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = resolve_db_path(params)
    session_id = args.get("session_id") or params.get("session_id")
    if session_id is not None and isinstance(session_id, str):
        session_id = session_id.strip() or None
    metric = (args.get("metric") or "duration").strip()
    limit = int(args.get("limit", params.get("limit", TRACE_ANALYZE_DEFAULT_ROW_LIMIT)))

    if not db_path.exists():
        print(json.dumps({"error": "Database not initialized"}))
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if session_id:
            cur = conn.execute(
                "SELECT id, session_id, timestamp, skill, action, metadata FROM traces WHERE session_id = ? ORDER BY timestamp",
                (session_id,),
            )
        else:
            cur = conn.execute(
                "SELECT id, session_id, timestamp, skill, action, metadata FROM traces ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    if not rows:
        scope = f"session {session_id}" if session_id else "global"
        print(json.dumps({"error": f"No traces found ({scope})"}))
        return

    scope = "session" if session_id else "global"
    if metric == "duration":
        durations = []
        for r in rows:
            meta = r.get("metadata")
            if isinstance(meta, str) and meta:
                try:
                    d = json.loads(meta)
                    dur = d.get("latency_ms", 0)
                except json.JSONDecodeError:
                    dur = 0
            else:
                dur = 0
            op = f"{r.get('skill','')}.{r.get('action','')}" or "unknown"
            durations.append((op, dur, r.get("id")))
        durations.sort(key=lambda x: x[1], reverse=True)
        total = sum(d for _, d, _ in durations)
        slowest = [
            {"operation": op, "duration_ms": d, "span_id": sid, "percentage": round(d / total * 100, 1) if total else 0}
            for op, d, sid in durations[:TRACE_ANALYZE_SLOWEST_OPS_COUNT]
        ]
        result = {
            "metric": "duration",
            "scope": scope,
            "total_duration_ms": total,
            "average_duration_ms": int(total / len(durations)) if durations else 0,
            "span_count": len(rows),
            "slowest_operations": slowest,
        }
    elif metric == "operations":
        ops = [f"{r.get('skill','')}.{r.get('action','')}" or "unknown" for r in rows]
        counts = Counter(ops)
        breakdown = [
            {"operation": op, "count": c, "percentage": round(c / len(rows) * 100, 1)}
            for op, c in counts.most_common()
        ]
        result = {
            "metric": "operations",
            "scope": scope,
            "total_operations": len(rows),
            "operation_breakdown": breakdown,
        }
    elif metric == "errors":
        errs = [r for r in rows if r.get("metadata") and "error" in str(r.get("metadata", "")).lower()]
        result = {
            "metric": "errors",
            "scope": scope,
            "total_spans": len(rows),
            "error_count": len(errs),
            "error_rate": round(len(errs) / len(rows) * 100, 1) if rows else 0,
            "errors": [
                {"id": r.get("id"), "skill": r.get("skill"), "action": r.get("action")}
                for r in errs[:TRACE_ANALYZE_ERROR_SAMPLE_MAX]
            ],
        }
    else:
        result = {"error": f"Unknown metric: {metric}. Use duration, operations, or errors."}

    print(json.dumps(result))


if __name__ == "__main__":
    main()
