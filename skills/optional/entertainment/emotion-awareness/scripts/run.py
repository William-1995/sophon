#!/usr/bin/env python3
"""
Emotion sub-agent run - retrieve emotion segments from DB.

Called when main agent invokes emotion-awareness.run (e.g. user asks "how's my mood").
Sub-agent perception (LLM) runs async after each chat; this script fetches stored segments.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

_project_root = Path(os.environ.get("SOPHON_ROOT", Path(__file__).resolve().parent.parent.parent.parent.parent))
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from db import emotion as db_emotion
from db.logs import insert as log_insert


def _parse_time(value: str, end_of_day: bool = False) -> float:
    """Accept YYYY-MM-DD or Unix timestamp. end_of_day shifts to 23:59:59 of that day."""
    try:
        return float(value)
    except ValueError:
        ts = datetime.strptime(str(value)[:10], "%Y-%m-%d").timestamp()
        return ts + 86399 if end_of_day else ts


def _resolve_params(params: dict) -> tuple[Path | None, str, str, float, int, str | None, str | None]:
    db_path_str = params.get("db_path")
    db_path = Path(db_path_str) if db_path_str else None
    session_id = (
        params.get("session_id") or params.get("_executor_session_id") or ""
    ).strip()
    args = params.get("arguments") or params
    scope = (args.get("scope") or "all").strip().lower()
    hours = float(args.get("hours") or 168.0)  # default 7 days for recent_hours
    limit = int(args.get("limit") or 50)
    since = str(args.get("since") or "").strip() or None
    until = str(args.get("until") or "").strip() or None
    return db_path, session_id, scope, hours, limit, since, until


def main() -> None:
    params = json.loads(sys.stdin.read())
    db_path, session_id, scope, hours, limit, since, until = _resolve_params(params)

    if not db_path or not db_path.exists():
        print(json.dumps({"error": "Database not configured or not found", "segments": [], "count": 0}))
        return

    if scope == "session":
        if not session_id:
            print(json.dumps({"error": "session_id is required for scope=session"}))
            return
        segments = db_emotion.query_by_session(db_path, session_id, limit=limit)
    elif scope == "range":
        if not since or not until:
            print(json.dumps({"error": "since and until are required for scope=range"}))
            return
        try:
            since_ts = _parse_time(since)
            until_ts = _parse_time(until, end_of_day=True)
        except Exception as exc:
            print(json.dumps({"error": f"Invalid date format: {exc}"}))
            return
        segments = db_emotion.query_range(
            db_path, since_ts=since_ts, until_ts=until_ts,
            session_id=session_id or None, limit=limit,
        )
    elif scope == "recent_hours":
        segments = db_emotion.query_by_time(db_path, hours=hours, limit=limit)
    else:
        # "all" or default: all sessions, ordered by time, no session filter
        segments = db_emotion.query_by_time(db_path, hours=None, limit=limit)

    if db_path.exists():
        extra: dict = {"scope": scope, "count": len(segments)}
        if scope == "recent_hours":
            extra["hours"] = hours
        elif scope == "range" and since and until:
            extra["since"] = since
            extra["until"] = until
        log_insert(
            db_path,
            "INFO",
            f"emotion-awareness.run scope={scope} segments={len(segments)}",
            session_id or "all",
            extra,
        )

    obs_lines = [f"Found {len(segments)} emotion segment(s)."]
    for i, s in enumerate(segments[:5], 1):
        label = s.get("emotion_label") or "unknown"
        summary = (s.get("combined_summary") or "")[:200]
        obs_lines.append(f"{i}. [{label}] {summary}")

    print(json.dumps({
        "segments": segments,
        "count": len(segments),
        "observation": "\n".join(obs_lines),
    }))


if __name__ == "__main__":
    main()
