#!/usr/bin/env python3
"""Troubleshoot diagnose - aggregates session traces and logs from DB. Produces A2UI format.

Skill subprocess: read one JSON object from stdin (parameters may be nested
under ``arguments`` or passed flat). Write one JSON object to stdout.
"""

import json
import sys
import time
from collections import Counter, defaultdict

from common.db_utils import check_db_exists, resolve_db_path, safe_db_connection


def _fetch_traces(params: dict, session_id: str | None, traces_limit: int) -> list[dict]:
    with safe_db_connection(resolve_db_path(params)) as conn:
        if session_id:
            cur = conn.execute(
                "SELECT skill, action, result_preview, timestamp FROM traces WHERE session_id = ? ORDER BY timestamp",
                (session_id,),
            )
        else:
            cur = conn.execute(
                "SELECT skill, action, result_preview, timestamp FROM traces ORDER BY timestamp DESC LIMIT ?",
                (traces_limit,),
            )
        return [dict(row) for row in cur.fetchall()]


def _fetch_logs(params: dict, session_id: str | None, logs_limit: int) -> list[dict]:
    with safe_db_connection(resolve_db_path(params)) as conn:
        if session_id:
            cur = conn.execute(
                "SELECT level, message, timestamp FROM logs WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, logs_limit),
            )
        else:
            cur = conn.execute(
                "SELECT level, message, timestamp FROM logs ORDER BY timestamp DESC LIMIT ?",
                (logs_limit,),
            )
        return [dict(row) for row in cur.fetchall()]


def _build_date_range(rows: list[dict]) -> dict | None:
    timestamps = [r.get("timestamp") for r in rows if r.get("timestamp") is not None]
    if not timestamps:
        return None
    try:
        min_ts, max_ts = min(timestamps), max(timestamps)
        return {
            "min_date": time.strftime("%Y-%m-%d", time.localtime(int(float(min_ts)))),
            "max_date": time.strftime("%Y-%m-%d", time.localtime(int(float(max_ts)))),
            "min_timestamp": min_ts,
            "max_timestamp": max_ts,
        }
    except (ValueError, OSError, TypeError):
        return None


def _build_summary(scope: str, traces: list[dict], logs: list[dict], question: str) -> str:
    summary = f"{scope}: {len(traces)} traces, {len(logs)} log entries. Question: {question}"
    errs = [l for l in logs if l.get("level") == "ERROR"]
    if errs:
        summary += f" Found {len(errs)} errors."
    return summary


def _build_by_level(logs: list[dict]) -> dict[str, int]:
    return dict(Counter(l.get("level") or "UNKNOWN" for l in logs)) if logs else {}


def _build_time_series(logs: list[dict]) -> list[dict[str, int | str]]:
    by_date: dict[str, int] = defaultdict(int)
    for row in logs:
        ts = row.get("timestamp")
        if ts is None:
            continue
        try:
            day = time.strftime("%Y-%m-%d", time.localtime(int(float(ts))))
            by_date[day] += 1
        except (ValueError, OSError, TypeError):
            continue
    return [{"date": k, "count": v} for k, v in sorted(by_date.items())]


def _build_operation_breakdown(traces: list[dict]) -> list[dict[str, int | str]]:
    ops = [f"{r.get('skill', '')}.{r.get('action', '')}".strip() or "unknown" for r in traces]
    counts = Counter(ops)
    return [{"operation": op, "count": c} for op, c in counts.most_common(15)]


def _build_charts(by_level: dict[str, int], time_series: list[dict], operation_breakdown: list[dict]) -> list[dict]:
    charts: list[dict] = []
    if operation_breakdown:
        charts.append({
            "kind": "operations",
            "labels": [x["operation"] for x in operation_breakdown],
            "values": [x["count"] for x in operation_breakdown],
        })
    if by_level:
        charts.append({
            "kind": "log_levels",
            "labels": list(by_level.keys()),
            "values": list(by_level.values()),
        })
    if time_series:
        charts.append({
            "kind": "time_series",
            "chart_type": "line",
            "x": [d["date"] for d in time_series],
            "y": [d["count"] for d in time_series],
        })
    return charts


def main() -> None:
    """Run the skill entrypoint (stdin JSON → stdout JSON)."""
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = resolve_db_path(params)
    session_id = args.get("session_id", params.get("session_id"))
    if session_id is not None and isinstance(session_id, str):
        session_id = session_id.strip() or None
    question = args.get("question", "")
    traces_limit = int(args.get("traces_limit", params.get("traces_limit", 1000)))
    logs_limit = int(args.get("logs_limit", params.get("logs_limit", 500)))

    if not check_db_exists(db_path):
        print(json.dumps({"error": "Database not initialized", "summary": ""}))
        return

    traces = _fetch_traces(params, session_id, traces_limit)
    logs = _fetch_logs(params, session_id, logs_limit)

    scope = f"session {session_id}" if session_id else "global"
    date_range_out = _build_date_range(traces + logs)
    summary = _build_summary(scope, traces, logs, question)
    by_level = _build_by_level(logs)
    time_series = _build_time_series(logs)
    operation_breakdown = _build_operation_breakdown(traces)

    out: dict = {
        "summary": summary,
        "traces_count": len(traces),
        "logs_count": len(logs),
    }
    if date_range_out:
        out["date_range"] = date_range_out
    if by_level:
        out["by_level"] = by_level
    if time_series:
        out["time_series"] = time_series
    if operation_breakdown:
        out["operation_breakdown"] = operation_breakdown

    charts = _build_charts(by_level, time_series, operation_breakdown)
    if charts:
        try:
            from core.a2ui import build_diagnose_a2ui
            surface_id = "diagnose"
            a2ui_messages = build_diagnose_a2ui(surface_id, summary, charts)
            out["gen_ui"] = {"format": "a2ui", "surfaceId": surface_id, "messages": a2ui_messages}
        except Exception:
            out["gen_ui"] = {"type": "bar", "payload": {"charts": charts}}

    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
