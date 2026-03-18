#!/usr/bin/env python3
"""Troubleshoot diagnose - aggregates session traces and logs from DB. Produces A2UI format."""
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# Load skill constants explicitly (troubleshoot doesn't import core, but keeps pattern consistent)
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "troubleshoot_constants",
    Path(__file__).resolve().parent.parent / "constants.py",
)
_c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_c)
DB_FILENAME = _c.DB_FILENAME


def _resolve_db_path(params: dict) -> Path:
    p = params.get("db_path")
    if p:
        return Path(p)
    return Path(params.get("workspace_root", "")) / DB_FILENAME


def main() -> None:
    params = json.loads(sys.stdin.read())
    args = params.get("arguments", params)
    db_path = _resolve_db_path(params)
    session_id = args.get("session_id", params.get("session_id"))
    if session_id is not None and isinstance(session_id, str):
        session_id = session_id.strip() or None
    question = args.get("question", "")
    traces_limit = int(args.get("traces_limit", params.get("traces_limit", 1000)))
    logs_limit = int(args.get("logs_limit", params.get("logs_limit", 500)))
    if not db_path.exists():
        print(json.dumps({"error": "Database not initialized", "summary": ""}))
        return
    conn = __import__("sqlite3").connect(str(db_path))
    conn.row_factory = __import__("sqlite3").Row
    traces = []
    logs = []
    try:
        if session_id:
            cur = conn.execute(
                "SELECT skill, action, result_preview FROM traces WHERE session_id = ? ORDER BY timestamp",
                (session_id,),
            )
            traces = [dict(r) for r in cur.fetchall()]
            cur = conn.execute(
                "SELECT level, message, timestamp FROM logs WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, logs_limit),
            )
            logs = [dict(r) for r in cur.fetchall()]
        else:
            cur = conn.execute(
                "SELECT skill, action, result_preview FROM traces ORDER BY timestamp DESC LIMIT ?",
                (traces_limit,),
            )
            traces = [dict(r) for r in cur.fetchall()]
            cur = conn.execute(
                "SELECT level, message, timestamp FROM logs ORDER BY timestamp DESC LIMIT ?",
                (logs_limit,),
            )
            logs = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    scope = f"session {session_id}" if session_id else "global"
    date_range_out: dict | None = None
    all_ts = [r.get("timestamp") for r in traces + logs if r.get("timestamp") is not None]
    if all_ts:
        try:
            min_ts, max_ts = min(all_ts), max(all_ts)
            date_range_out = {
                "min_date": time.strftime("%Y-%m-%d", time.localtime(int(float(min_ts)))),
                "max_date": time.strftime("%Y-%m-%d", time.localtime(int(float(max_ts)))),
                "min_timestamp": min_ts,
                "max_timestamp": max_ts,
            }
        except (ValueError, OSError, TypeError):
            pass
    summary = f"{scope}: {len(traces)} traces, {len(logs)} log entries. Question: {question}"
    by_level: dict[str, int] = {}
    time_series: list[dict[str, str | int]] = []
    operation_breakdown: list[dict[str, str | int]] = []

    if logs:
        level_counts = Counter(l.get("level") or "UNKNOWN" for l in logs)
        by_level = dict(level_counts)
        errs = [l for l in logs if l.get("level") == "ERROR"]
        if errs:
            summary += f" Found {len(errs)} errors."
        by_date: dict[str, int] = defaultdict(int)
        for row in logs:
            ts = row.get("timestamp")
            if ts:
                try:
                    day = time.strftime("%Y-%m-%d", time.localtime(int(float(ts))))
                    by_date[day] += 1
                except (ValueError, OSError, TypeError):
                    pass
        time_series = [{"date": k, "count": v} for k, v in sorted(by_date.items())]

    if traces:
        ops = [f"{r.get('skill', '')}.{r.get('action', '')}".strip() or "unknown" for r in traces]
        counts = Counter(ops)
        operation_breakdown = [
            {"operation": op, "count": c} for op, c in counts.most_common(15)
        ]

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
    if charts:
        try:
            from core.a2ui import build_diagnose_a2ui
            surface_id = "diagnose"
            a2ui_messages = build_diagnose_a2ui(surface_id, summary, charts)
            out["gen_ui"] = {"format": "a2ui", "surfaceId": surface_id, "messages": a2ui_messages}
        except Exception:
            out["gen_ui"] = {"type": "bar", "payload": {"charts": charts}}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
